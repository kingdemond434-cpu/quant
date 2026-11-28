"""The LIVE `cot_positioning` sleeve keeps its identity; the flow logic is its own family.

THE DEFECT THIS PINS (#238 audit HOLD, 2026-10-07). The PR widened `family_cot_positioning` with
series/transform/mode arguments. `shadow_forward` freezes `sleeve_registry.code_hash` (the
function's source from its `def` line) and `sleeve_registry.behaviour_hash` (its bytecode) for
every forward clock and `verify()`s both each cycle; the widened function moved both, so the LIVE
`EURUSD.cot_positioning` sleeve would have read IDENTITY_BROKEN and its forward window would
have reset. Measured on the PR head 40ee73dac: code_hash bd66df4dcb65a6dd (LIVE 7a57ee8bf3b231cf)
and, under the box's Python 3.14, behaviour_hash d9d111c8f3c6f6b5 (LIVE 5ea0f82d1bd1b7f0).

The repair restores `family_cot_positioning` byte-identical to LIVE and moves the change/flow
construction into `family_cot_positioning_flow`, registered beside it. This file computes both
hashes the way `shadow_forward` does -- resolve the constructor with `shadow_forward._family_fn`,
hash it with `sleeve_registry.code_hash` / `behaviour_hash` -- and asserts LIVE's values.

`behaviour_hash` hashes CPython bytecode, so its value is per interpreter minor version. LIVE's
value is pinned for each version it was measured under (the same source compiled by 3.11, 3.12,
3.13 and 3.14); the 3.14 value is the one the box froze into `sleeve_registry.json`.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import sleeve_registry  # noqa: E402

#: LIVE (claude/llm-auto-upgrade-verify-gcjac3 at 87a1bdac3) `family_cot_positioning`.
LIVE_CODE_HASH = "7a57ee8bf3b231cf"
LIVE_BEHAVIOUR_HASH = {
    (3, 11): "58328581d474ca8e",
    (3, 12): "9e2f29d8715c6c26",
    (3, 13): "7614a3542a207f00",
    (3, 14): "5ea0f82d1bd1b7f0",
}
LIVE_SLEEVE = "EURUSD.cot_positioning.continuous#input_source=cot_point_in_time"


def _live_constructor():
    """The constructor exactly as the forward clock resolves it."""
    import shadow_forward
    fn = shadow_forward._family_fn("cot_positioning")
    assert fn is not None
    return fn


def test_live_family_code_hash_equals_live():
    fn = _live_constructor()
    assert sleeve_registry.code_hash(fn) == LIVE_CODE_HASH


def test_live_family_behaviour_hash_equals_live():
    ver = sys.version_info[:2]
    if ver not in LIVE_BEHAVIOUR_HASH:
        pytest.skip(f"LIVE's behaviour hash was not measured under Python {ver}; the code hash "
                    "(source identity) still binds")
    assert sleeve_registry.behaviour_hash(_live_constructor()) == LIVE_BEHAVIOUR_HASH[ver]


def test_live_sleeve_frozen_identity_still_verifies():
    """The box's frozen identity for the LIVE sleeve agrees with this tree's function."""
    reg = sleeve_registry.REGISTRY
    try:
        doc = json.loads(reg.read_text("utf-8"))
    except (OSError, ValueError):
        pytest.skip(f"{reg.name} unreadable on this tree")
    rows = doc.get("sleeves", doc) if isinstance(doc, dict) else {}
    row = rows.get(LIVE_SLEEVE) if isinstance(rows, dict) else None
    if not isinstance(row, dict):
        pytest.skip(f"{LIVE_SLEEVE} is not in {reg.name} on this tree")
    ident = row.get("identity") or {}
    fn = _live_constructor()
    assert ident.get("code_hash") == sleeve_registry.code_hash(fn) == LIVE_CODE_HASH
    if sys.version_info[:2] == (3, 14) and ident.get("behaviour_hash"):
        assert ident["behaviour_hash"] == sleeve_registry.behaviour_hash(fn)
    assert ident.get("behaviour_hash") in (None, "", LIVE_BEHAVIOUR_HASH[(3, 14)])


def test_live_family_signature_is_the_level_construction():
    params = list(inspect.signature(_live_constructor()).parameters)
    assert params == ["df", "cot", "lookback_weeks", "extreme_pct", "atr_n", "stop_atr", "rr",
                      "ttl_bars"]


def test_flow_is_its_own_registered_family():
    import shadow_forward
    from mt5desk import families_orthogonal as fo
    from research.gauntlet_buildability import BUILDABLE, family_verdict
    from research.orthogonal_sweep import NOT_SOURCED_HERE

    from libs.research.alpha_clusters import classify_family
    flow = fo.ORTHOGONAL_FAMILIES["cot_positioning_flow"]
    assert flow is fo.family_cot_positioning_flow
    assert flow is not fo.ORTHOGONAL_FAMILIES["cot_positioning"]
    assert shadow_forward._family_fn("cot_positioning_flow") is flow
    assert sleeve_registry.code_hash(flow) != LIVE_CODE_HASH
    assert classify_family("cot_positioning_flow") == "positioning_flow"
    # the sealed build_cell has no COT branch for it; it needs none (it loads by cot_symbol)
    assert family_verdict("cot_positioning_flow")[0] == BUILDABLE
    # its trials are the proposer's grid, never a second uncharged sweep at its defaults
    assert "cot_positioning_flow" in NOT_SOURCED_HERE
    assert "cot_positioning_flow" in fo.FAMILY_INPUTS


def test_the_proposer_never_builds_the_live_family():
    src = (_DESK / "research" / "cot_positioning_flow.py").read_text("utf-8")
    assert "family_cot_positioning(" not in src
    assert 'FAMILY = "cot_positioning_flow"' in src
