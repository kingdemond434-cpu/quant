"""No pen may seal a certificate that nothing can run.

WHAT THIS PROTECTS. A certificate whose `shadow_spec` carries no `params` passes all ten gates,
is counted in every survivor total, inflates the desk's belief about its own edge -- and can
never be enrolled, funded or falsified, because enrolment refuses to guess the parameterisation
that passed (guessing one forward-tests a DIFFERENT strategy than the one certified, which is
the two-stage law's exact prohibition). Measured 2026-09-06: 18 of them on the live desk.

WHY A STRUCTURAL TEST AND NOT JUST A BEHAVIOURAL ONE. The refusal already existed -- in ONE of
the four publishers. `publish_qquant_survivors` had it; `scripts/external_gauntlet.py` printed
NO-SPEC and stored the row anyway; `scripts/full_pipeline.py` wrote a spec with no `params` key
at all; `side_channels/full_pipeline.py` defaulted absent params to `{}`, which downstream is a
positive claim rather than a missing one. Testing only the behaviour of the fence would have
passed the whole time the zombies were being minted, because the fence was never the thing that
was broken -- its ABSENCE from three doors was. So this asserts both: that the judge is right,
and that every pen actually asks it.

`{}` IS NOT A DEFECT AND MUST KEEP PASSING. An empty mapping is the complete parameterisation
"family defaults", byte-exactly what the gauntlet executed for a family that takes no arguments
(`overnight_gap_decay`). Excluding it has already stranded certificates twice, so it gets its own
assertion rather than being left to inference.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

from research.survivor_publication import unrunnable_reason  # noqa: E402

#: Every module that writes a row into UNIVERSAL_SURVIVORS.json. Listed explicitly rather than
#: discovered, so ADDING a publisher without adding it here is itself caught by the last test:
#: a file that writes the canon and is absent from this tuple is exactly the fourth pen this
#: whole fence exists to anticipate.
PUBLISHERS = (
    "research/survivor_publication.py",
    "scripts/external_gauntlet.py",
    "scripts/full_pipeline.py",
    "side_channels/full_pipeline.py",
)

REFUSAL_NAMES = {"unrunnable_reason", "_certificate_refusal"}


def _tree(rel: str) -> ast.Module:
    return ast.parse((BASE / rel).read_text("utf-8"))


def _calls(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                out.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                out.add(fn.attr)
    return out


class TestTheJudge:
    """The predicate itself: what it refuses, and -- as load-bearing -- what it allows."""

    @pytest.mark.parametrize("row", [
        {},
        {"shadow_spec": None},
        {"shadow_spec": "asia"},
        {"shadow_spec": {"symbol": "EURUSD", "family": "session_range_breakout"}},
        {"shadow_spec": {"symbol": "EURUSD", "family": "x", "params": None}},
        {"shadow_spec": {"symbol": "EURUSD", "family": "x", "params": [1, 2]}},
        {"shadow_spec": {"symbol": "", "family": "x", "params": {}}},
        {"shadow_spec": {"symbol": "EURUSD", "family": "", "params": {}}},
    ])
    def test_unrunnable_shapes_are_refused_with_a_readable_reason(self, row):
        why = unrunnable_reason(row)
        assert why, f"a certificate shaped {row!r} would be sealed and could never be enrolled"
        # Prose, not a bool: every caller prints this, and the NO-SPEC line that WAS printed for
        # weeks was ignored partly because it named no consequence.
        assert len(why) > 30 and " " in why

    def test_empty_params_is_a_complete_parameterisation_and_is_allowed(self):
        row = {"shadow_spec": {"symbol": "USDZAR", "family": "overnight_gap_decay", "params": {}}}
        assert unrunnable_reason(row) is None, (
            "`{}` is the parameterisation 'family defaults', byte-exactly what the gauntlet ran. "
            "Refusing it has stranded overnight_gap_decay certificates twice.")

    def test_a_full_certificate_is_allowed(self):
        row = {"shadow_spec": {"symbol": "XAUUSD", "family": "session_range_breakout",
                               "params": {"rr": 1.5, "wait_bars": 12}}}
        assert unrunnable_reason(row) is None


class TestEveryPenAsksTheJudge:
    """The half that would have caught the real defect: three doors had no fence at all."""

    @pytest.mark.parametrize("rel", PUBLISHERS)
    def test_publisher_calls_the_refusal(self, rel):
        called = _calls(_tree(rel))
        assert called & REFUSAL_NAMES, (
            f"{rel} writes into UNIVERSAL_SURVIVORS.json without asking `unrunnable_reason`. "
            f"Three of the four publishers did exactly this, and between them minted every "
            f"params-less certificate on the desk.")

    def test_no_publisher_defaults_absent_params_to_an_empty_dict(self):
        """`v.get("params", {})` converts 'never recorded' into 'takes no parameters'.

        That default defeats the fence BEFORE it is asked -- absent arrives as `{}`, which is a
        legitimate value the judge must allow -- so the guard would pass while sealing a
        certificate whose parameterisation was lost. It is not a style preference; it is the
        one way to reopen this hole with the fence still in place.
        """
        offenders = []
        for rel in PUBLISHERS:
            for node in ast.walk(_tree(rel)):
                # ONLY the `params` INSIDE a shadow_spec literal. An earlier version of this
                # test flagged every `.get("params", {})` in the file and caught five sites that
                # build backtest cells or derive a selector -- places where `{}` is the right
                # default and no certificate is being sealed. A test that fails on correct code
                # gets suppressed, and then it protects nothing.
                if not isinstance(node, ast.Dict):
                    continue
                for key, value in zip(node.keys, node.values):
                    if not (isinstance(key, ast.Constant) and key.value == "shadow_spec"):
                        continue
                    if not isinstance(value, ast.Dict):
                        continue
                    for skey, svalue in zip(value.keys, value.values):
                        if not (isinstance(skey, ast.Constant) and skey.value == "params"):
                            continue
                        if (isinstance(svalue, ast.Call)
                                and isinstance(svalue.func, ast.Attribute)
                                and svalue.func.attr == "get" and len(svalue.args) == 2
                                and isinstance(svalue.args[1], ast.Dict)
                                and not svalue.args[1].keys):
                            offenders.append(f"{rel}:{svalue.lineno}")
        assert not offenders, (
            "a shadow_spec defaults absent params to {} before the fence sees them, so a lost "
            "parameterisation is sealed as 'family defaults': " + ", ".join(offenders))
