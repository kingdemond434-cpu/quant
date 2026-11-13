"""The box's seed-miner leg runs clear-access sources only (Auditor HOLD on #602).

`hourly_cycle` starts `seed_miners.py --clear-access-only`. Under that switch a source outside
`seed_miners.CLEAR_ACCESS` is SET_ASIDE by name: its miner is never called, its wall is never
probed, and no seat file is written for it. Without the switch the sweep is unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "side_channels"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import seed_miners as sm  # noqa: E402


@pytest.fixture
def sweep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """seed_miners pointed at a temp intelligence root, every miner and every request recorded."""
    seen: dict[str, list[str]] = {"ran": [], "fetched": [], "probed": []}
    intel = tmp_path / "intelligence"
    intel.mkdir()
    monkeypatch.setattr(sm, "INTEL", intel)
    monkeypatch.setattr(sm, "STATE", intel / "seed_miners_state.json")

    def _miner(name: str):
        def run() -> list[dict]:
            seen["ran"].append(name)
            return [sm.row(name, "test", f"{name} row")]
        return run

    monkeypatch.setattr(sm, "MINERS", {n: _miner(n) for n in sm.MINERS})
    monkeypatch.setattr(sm, "fetch", lambda url, *a, **k: seen["fetched"].append(url) or "")
    monkeypatch.setattr(
        sm, "_probe_wall", lambda name, wall: seen["probed"].append(name) or (False, "test"))
    # The optional proposer seat and the cohort join are not what is under test.
    monkeypatch.setitem(sys.modules, "cohort_and_identity", None)
    from libs.research import proposer_seat as ps

    def _no_seat(*a: object, **k: object) -> None:
        raise RuntimeError("no panel in tests")

    monkeypatch.setattr(ps, "ask", _no_seat)
    return seen


def test_clear_access_only_runs_the_allow_list_and_sets_the_rest_aside(sweep, tmp_path) -> None:
    res = sm.run_and_save(clear_access_only=True)
    assert set(sweep["ran"]) == set(sm.CLEAR_ACCESS)
    assert sweep["probed"] == [] and sweep["fetched"] == []        # no wall is probed either
    aside = set(sm.MINERS) - set(sm.CLEAR_ACCESS)
    assert aside and all(res[n] == {"status": "SET_ASIDE", "why": sm.SET_ASIDE_WHY}
                         for n in aside)
    intel = tmp_path / "intelligence"
    assert {p.name for p in intel.iterdir() if p.is_dir()} == set(sm.CLEAR_ACCESS)
    st = json.loads((intel / "seed_miners_state.json").read_text("utf-8"))
    assert st["last_sweep"]["clear_access_only"] is True
    assert st["last_sweep"]["set_aside"] == sorted(aside)
    latest = json.loads((intel / "latest_discoveries.json").read_text("utf-8"))
    assert all(latest[n]["status"] == "SET_ASIDE" for n in aside)
    assert all(latest[n]["count"] == 1 for n in sm.CLEAR_ACCESS)


def test_every_walled_and_every_scraped_source_is_outside_the_allow_list() -> None:
    assert set(sm.MINERS) >= sm.CLEAR_ACCESS
    assert not (sm.CLEAR_ACCESS & set(sm.SOURCE_WALLS))
    assert {"quant_se", "arxiv_qfin", "bis_speeches", "github_topics", "broker_swaps",
            "research_feeds", "github_depth"} == sm.CLEAR_ACCESS


def test_without_the_switch_the_sweep_is_unchanged(sweep) -> None:
    res = sm.run_and_save()
    walled = set(sm.SOURCE_WALLS) & set(sm.MINERS)
    assert set(sweep["ran"]) == set(sm.MINERS) - walled
    assert set(sweep["probed"]) == walled
    assert not [n for n, r in res.items() if r.get("status") == "SET_ASIDE"]


def test_the_set_aside_publishes_its_two_sided_missed_growth_line(sweep, tmp_path) -> None:
    """Rule 1: the set-aside is billed. Cost and gain both written, neither priced as zero, and
    the desk's missed-growth report carries them from the state file."""
    from research import missed_growth as mg

    state = tmp_path / "intelligence" / "seed_miners_state.json"
    assert mg.organ_published_lines(state)["verdict"] == "UNMEASURED"      # never ran: said
    sm.run_and_save(clear_access_only=True)
    aside = sorted(set(sm.MINERS) - set(sm.CLEAR_ACCESS))
    lines = json.loads(state.read_text("utf-8"))["missed_growth"]
    assert [ln["side"] for ln in lines] == ["cost", "gain"]
    cost, gain = lines
    assert cost["rail"] == gain["rail"] == "seed_miners_clear_access"
    assert cost["sources"] == aside and cost["n_sources"] == gain["n_sources"] == len(aside)
    for ln in lines:                                   # UNMEASURED is the answer, not a zero
        assert ln["value"] is None and ln["verdict"] == "UNMEASURED"
        assert ln["e_log_w"] == "UNMEASURED" and ln["at"] and ln["day"] == ln["at"][:10]
    carried = mg.organ_published_lines(state)
    assert carried["verdict"] == "UNMEASURED" and carried["n_lines"] == 2
    assert carried["lines"] == lines


def test_a_sweep_that_sets_nothing_aside_publishes_no_line(sweep, tmp_path) -> None:
    from research import missed_growth as mg

    state = tmp_path / "intelligence" / "seed_miners_state.json"
    sm.run_and_save(clear_access_only=True)
    sm.run_and_save()                                  # the next sweep replaces the line
    assert json.loads(state.read_text("utf-8"))["missed_growth"] == []
    assert mg.organ_published_lines(state)["verdict"] == "NOT_BINDING"


def test_the_missed_growth_report_reads_the_seed_miners_state_file() -> None:
    from research import missed_growth as mg

    assert mg.SEED_MINERS_STATE == sm.STATE
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"seed_miners_clear_access": organ_published_lines(' in src


def test_the_archive_sources_are_named_as_still_set_aside() -> None:
    assert not ({"darwinex", "forextsd_cdx", "ff_calendar_vintage"} & sm.CLEAR_ACCESS)
    assert {"darwinex", "forextsd_cdx", "ff_calendar_vintage"} <= set(sm.MINERS)


def test_the_command_line_switch_is_the_one_the_hourly_leg_passes() -> None:
    src = (_DESK / "side_channels" / "seed_miners.py").read_text("utf-8")
    assert 'run_and_save(clear_access_only="--clear-access-only" in sys.argv[1:])' in src
    hc = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"side_channels/seed_miners.py", "--clear-access-only"' in hc
