"""THE DASHBOARD'S PROMOTION COUNTER MUST SEE EVERY LANE, NOT THE ONE THAT PICKED ITS SEPARATOR.

WHAT HAPPENED. Three lanes write a promotion verdict and they do not agree on one character:

    desks/mt5/research/shadow_forward.py    "PROMOTION CANDIDATE"    (space)
    desks/mt5/research/scalp_shadow.py      "PROMOTION_CANDIDATE"    (underscore)
    desks/mt5/research/qquant_shadow.py     "PROMOTION_CANDIDATE"    (underscore)

`build_zentech_state` counted `status == "PROMOTION CANDIDATE"` -- the space form only. So every
candidate the SCALP and QQUANT lanes ever produced was invisible to the tile, and the dashboard
reported `promotion_ready: 0` while `promoter.promote_scalp`, which matches the underscore form
correctly, was reading the same rows and seeing candidates.

THE COST WAS NOT COSMETIC. The principal was told, repeatedly and over days, that no sleeve was
promotable -- by a number that could not see two of the three lanes. Two gold scalp sleeves were
the specific thing being asked about. A counter that silently covers a subset of its population
is worse than no counter: it answers confidently and it answers wrong.

The fix normalises on READ rather than adding a second literal, because the next lane will also
choose its own separator and no reader should have to know which. `_is_terminal` immediately below
it in the same file already carries this lesson from a rename one year earlier -- "a retirement
that does not propagate is a rename, not a retirement" -- and the promotion counter never got it.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_bzs", _ROOT / "scripts" / "build_zentech_state.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bzs():
    return _load()


@pytest.mark.parametrize("written", ["PROMOTION CANDIDATE", "PROMOTION_CANDIDATE",
                                     "promotion_candidate", "Promotion Candidate"])
def test_every_separator_a_lane_may_choose_is_counted(bzs, written: str) -> None:
    """The exact defect. Each of these is the same verdict; none may be invisible."""
    assert bzs._norm_status(written) == "PROMOTION CANDIDATE", (
        f"{written!r} does not normalise to the counted form -- a lane writing it would be "
        "invisible to the dashboard's promotion tile, which is how two gold scalp sleeves were "
        "reported as 'not promotable' for days")


def test_the_lanes_on_this_tree_all_normalise_to_the_counted_form(bzs) -> None:
    """Read the real lane sources rather than trusting the list above.

    A test that hardcodes the three known spellings passes forever after a fourth lane lands with
    a fifth spelling. This greps what the lanes ACTUALLY write today, so a new lane with a new
    separator fails here rather than going quiet on the dashboard.
    """
    import re

    lanes = sorted((_ROOT / "desks" / "mt5" / "research").glob("*shadow*.py"))
    assert lanes, "no shadow lanes found -- the glob is wrong and this test proves nothing"
    seen: dict[str, str] = {}
    for lane in lanes:
        for raw in re.findall(r'"(PROMOTION[ _]CANDIDATE)"', lane.read_text("utf-8")):
            seen[lane.name] = raw
            assert bzs._norm_status(raw) == "PROMOTION CANDIDATE", (
                f"{lane.name} writes {raw!r}, which the dashboard counter cannot see")
    assert seen, "no lane writes a promotion verdict -- the pattern has drifted"


def test_terminal_detection_survives_the_normalisation(bzs) -> None:
    """Normalising must not accidentally revive a retired clock.

    `_is_terminal` matches by PREFIX on an upper-cased string, and the normaliser now also
    replaces underscores -- so RETIRED_ORPHAN becomes RETIRED ORPHAN. The prefix still holds, and
    this asserts it rather than assuming it: a retired sleeve counting as a live forward clock is
    the failure that produced 31 phantom clocks the last time this file was wrong.
    """
    for retired in ("RETIRED_ORPHAN", "RETIRED_GATE_FAIL", "RETIRED_UNRECONSTRUCTIBLE",
                    "KILL", "PROMOTED"):
        assert bzs._is_terminal(bzs._norm_status(retired)), f"{retired} stopped reading terminal"
    for live in ("ACTIVE", "ACCUMULATING", "PROMOTION_CANDIDATE", "WAITING_FOR_FORWARD_BARS"):
        assert not bzs._is_terminal(bzs._norm_status(live)), f"{live} wrongly reads terminal"


def test_a_scalp_candidate_is_counted_end_to_end(bzs, tmp_path, monkeypatch) -> None:
    """The whole path, not just the helper: a scalp lane row must reach `promotion_ready`.

    The unit above proves the normaliser is right. This proves the COUNTER uses it -- which is the
    half that was broken, and the half a helper test would have kept passing through.
    """
    desk = tmp_path / "desks" / "mt5"
    (desk / "reports" / "shadow").mkdir(parents=True)
    (desk / "data").mkdir(parents=True)
    (desk / "reports" / "shadow" / "scalp_shadow_state.json").write_text(json.dumps({
        "sleeves": {
            "gold_scalp_m5_asia": {"status": "PROMOTION_CANDIDATE", "n": 63,
                                   "expectancy_r": 0.31, "days_active": 11,
                                   "promotion_authority": True, "matured": True},
            "gold_scalp_m15_london": {"status": "PROMOTION_CANDIDATE", "n": 51,
                                      "expectancy_r": 0.22, "days_active": 9,
                                      "promotion_authority": True, "matured": True},
            "gold_scalp_m5_ny": {"status": "ACCUMULATING", "n": 8, "expectancy_r": 0.4},
        }}), "utf-8")
    monkeypatch.setattr(bzs, "ROOT", tmp_path)
    monkeypatch.setattr(bzs, "DESK", desk)

    out = bzs._funnel({"n": 0})
    assert out["promotion_ready"] == 2, (
        f"two matured scalp candidates, counter says {out['promotion_ready']} -- the tile is "
        "blind to the lane again")
    assert set(out.get("promotion_ready_names") or []) == {
        "gold_scalp_m5_asia", "gold_scalp_m15_london"}, (
        "the counter must NAME what it counted; a bare number is what let this hide")


def test_a_scalp_sleeves_real_day_count_reaches_the_dashboard(bzs, tmp_path, monkeypatch) -> None:
    """`days_active` vs `days` -- the same defect as the status separator, one field over.

    `shadow_forward` and `qquant_shadow` publish `days_active`; `scalp_shadow` published `days`.
    The tile read only the first, so three gold scalp sleeves that had been on their forward
    clock since 2026-08-22 displayed as `day 0/14` for a fortnight -- reading, to anyone looking,
    as if they had only just started and had thirteen more days to wait.
    """
    desk = tmp_path / "desks" / "mt5"
    (desk / "reports" / "shadow").mkdir(parents=True)
    (desk / "data").mkdir(parents=True)
    (desk / "reports" / "shadow" / "scalp_shadow_state.json").write_text(json.dumps({
        "sleeves": {
            # No forward_start, so the tile must fall back to the row's own day count -- which is
            # the exact path that was reading the wrong field name.
            "xau_m15_anti_breakout": {"status": "ACCUMULATING", "n": 0, "n_historical": 69,
                                      "days": 14, "expectancy_r": None},
        }}), "utf-8")
    monkeypatch.setattr(bzs, "ROOT", tmp_path)
    monkeypatch.setattr(bzs, "DESK", desk)

    row = next(r for r in bzs._funnel({"n": 0})["forward_detail"]
               if r["name"] == "xau_m15_anti_breakout")
    assert row["days"] == 14, (
        f"the scalp sleeve reports day {row['days']}/14 when its lane says 14 -- the tile is "
        "reading `days_active` only again, and a sleeve at the gate looks like one that just "
        "started")


def test_the_lane_publishes_both_day_field_names(bzs) -> None:
    """Fixed at the WRITER too, not only the reader.

    Normalising the reader fixes today's dashboard; publishing both names is what stops the next
    consumer -- a fence, a script, an export -- rediscovering the same zero. Neither half alone is
    the fix: the reader must be tolerant AND the writer must be conventional.
    """
    src = (_ROOT / "desks" / "mt5" / "research" / "scalp_shadow.py").read_text("utf-8")
    assert '"days_active": days' in src, (
        "scalp_shadow no longer publishes days_active; every consumer that knows only the "
        "convention will read 0 for a sleeve that has been running for weeks")


def test_an_empty_forward_count_says_why_it_is_empty(bzs) -> None:
    """Zero must distinguish "quiet market" from "this sleeve has no clock at all".

    Both publish n=0 and demand opposite responses: one waits, the other means the state file is
    not persisting and the sleeve can never mature however many trades it takes. Three gold scalp
    sleeves sat at n=0 with 39/65/69 observations tagged historical and nothing said which.
    """
    src = (_ROOT / "desks" / "mt5" / "research" / "scalp_shadow.py").read_text("utf-8")
    assert '"forward_empty_reason"' in src, "a zero forward count is unexplained again"
    assert "no prior clock for this sleeve" in src and "no trade has occurred since" in src, (
        "the two zero-causes are not distinguished; that is the whole point of the field")
