"""Every decision-affecting producer is named by something that RUNS it.

THE LESSON THIS ENFORCES. When several unrelated organs go stale together, the cause is the
SCHEDULER, not each organ -- every ops/crontab.manifest row died with root cron on 2026-08-20 and
each stale artifact then collected its own bespoke diagnosis. The same shape recurred on
2026-09-05 in the other direction: five organs were found that had never been scheduled at all
(the deepening worker, the clock healer, edge_search, orthogonal_sweep and the miner candidate
compiler -- the single step between what the crawlers fetch and what the gauntlet can judge). A
dashboard reporting "37.7h old (hourly leg)" was describing INTENT; nothing hourly existed.

`scripts/check_producer_schedules.py` converts that from something a reader has to notice into
something a run asserts. These tests are what stop the fence itself from going quiet.

    enforces docs/desk_lessons.jsonl L0175
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    path = _ROOT / "scripts" / "check_producer_schedules.py"
    spec = importlib.util.spec_from_file_location("_check_producer_schedules", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cps():
    return _load()


def test_no_decision_affecting_producer_is_unscheduled(cps) -> None:
    """The live verdict, at the ratchet. If this fails, an organ was added that nothing runs."""
    out = cps.check()
    assert out["status"] != "BREACH", out["problems"]
    assert len(out["unscheduled"]) <= cps.MAX_UNSCHEDULED, out["unscheduled"]


def test_the_ratchet_is_at_its_floor(cps) -> None:
    """MAX_UNSCHEDULED may fall and must never rise. Pinned so a future edit that raises it to
    make a red run green has to argue with a test rather than with a comment."""
    assert cps.MAX_UNSCHEDULED == 0


def test_every_exemption_carries_a_reason(cps) -> None:
    """An exemption without a reason is not an exemption -- it is an unscheduled organ with a
    note. The reason is what a reader checks against reality later."""
    for name, why in cps.EVENT_DRIVEN.items():
        assert why and len(why) > 40, f"{name} is exempted with no usable reason"


def test_the_scheduler_surfaces_all_exist(cps) -> None:
    """A surface path that has been renamed silently narrows the fence: nodes scheduled ONLY on
    the missing surface start reading as unscheduled, or -- far worse if the list is used the
    other way round -- a node is called scheduled because a surface that no longer exists once
    named it. Either way the fence stops describing the desk."""
    missing = [rel for rel in cps.SURFACES if not (_ROOT / rel).exists()]
    assert not missing, f"scheduler surface(s) named by the fence do not exist: {missing}"


def test_the_fence_can_actually_fail(cps, monkeypatch) -> None:
    """L1.28a. Point the fence at a tree with NO scheduler surfaces: every node must come back
    unscheduled. If it comes back clean, the substring match is passing on something other than
    the surfaces -- and the green verdict above means nothing."""
    monkeypatch.setattr(cps, "_surfaces_text", lambda root: "")
    out = cps.check()
    assert out["status"] == "BREACH", (
        "with no scheduler surface readable at all, every producer is unscheduled; a clean "
        "verdict here means the fence is not reading the surfaces it claims to read")
    assert out["unscheduled"], out


def test_a_scheduled_node_is_recognised_by_name(cps, monkeypatch) -> None:
    """The positive direction: naming a node on a surface must be what clears it, so the fence
    cannot be satisfied by an unrelated line that happens to sit in the same file."""
    from libs.ops.capability_graph import NODES, stages

    st = stages()
    target = next(n.name for n in NODES
                  if (st.get(n.name) or {}).get("decision_affecting")
                  and n.name not in cps.EVENT_DRIVEN)
    monkeypatch.setattr(cps, "_surfaces_text", lambda root: f"{target}\n")
    out = cps.check()
    assert target not in out["unscheduled"]
    assert out["scheduled"] == 1, "exactly the named node should have cleared"
