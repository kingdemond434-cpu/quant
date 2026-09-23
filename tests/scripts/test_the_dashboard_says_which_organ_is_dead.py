"""A board that says LATE while one organ has been dead three weeks is telling the truth badly.

MEASURED 2026-09-09. `gateway_state.json` had not been written since 2026-08-17 -- TWENTY-THREE
DAYS -- and the dashboard's headline read `box: LATE, 2.1h`. Both were correct. `_box_liveness`
takes the FRESHEST clock across the box's artifacts deliberately, and its own docstring gives the
reason: "one organ dying is a defect in that organ; ALL of them stopping is the machine." The
shadow sync was 2.1 hours old, so the machine was late. It was also true that the organ holding
the capital had not run in three weeks.

NOTHING WAS UNMEASURED. `per_report` carried `gateway_state.json: age_seconds 2049285` the whole
time. Two things hid it:

    ORDER   the reader had to already suspect the gateway to go and look for it, and the
            headline pointed at a different, milder fact.
    LADDER  `per_report` grades FRESH or STALE. Forty-six minutes and twenty-three days print
            the same word, so the one number that mattered was rendered as the routine case.

This block is therefore not a new measurement -- it re-reads the same evidence with a ladder and
an order. That is what the failure needed. `test_a_dead_organ_outranks_a_late_one_in_the_headline`
is the test that would have caught it, and it fails on the old shape by construction: the old
shape has no headline at all.

ABSENCE IS NEVER A PASS (L1.28a) and it must not be quiet either. An artifact with no clock ranks
ABOVE stale here, because an organ nobody can see could be any age at all, including dead since
before anyone looked.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_bzs_organs", _ROOT / "scripts" / "build_zentech_state.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bzs():
    return _load()


NOW = datetime(2026, 9, 9, 17, 19, tzinfo=UTC)


def _tree(bzs, tmp_path, monkeypatch, ages: dict[str, timedelta | None],
          failing: tuple[str, ...] = ()) -> Path:
    """A desk tree whose named artifacts last wrote `ages` ago. None writes the file with no clock.

    Keyed by the artifact's basename, which is how `_box_liveness` reports it.
    """
    desk = tmp_path / "desks" / "mt5"
    (desk / "reports" / "shadow").mkdir(parents=True)
    (desk / "data").mkdir(parents=True)
    rel_for = {rel.rsplit("/", 1)[-1]: (rel, fields) for rel, fields in bzs.BOX_REPORTS}
    for name, age in ages.items():
        rel, fields = rel_for[name]
        body = {} if age is None else {fields[0]: (NOW - age).isoformat()}
        (desk / rel).write_text(json.dumps(body), "utf-8")
    if failing:
        (desk / "data" / "stall_watch.json").write_text(json.dumps(
            {"checked_at": NOW.isoformat(),
             "procs": {f"fail.{t}": {"cpu": 1} for t in failing}}), "utf-8")
    monkeypatch.setattr(bzs, "ROOT", tmp_path)
    monkeypatch.setattr(bzs, "DESK", desk)
    return desk


def _by_organ(got: dict) -> dict[str, str]:
    return {r["organ"]: r["verdict"] for r in got["rows"]}


# ------------------------------------------------------------------- THE FAILURE, REPRODUCED
def test_a_dead_organ_outranks_a_late_one_in_the_headline(bzs, tmp_path, monkeypatch) -> None:
    """THE EXACT 2026-09-09 STATE. Machine LATE at 2.1h, gateway dead 23 days. The headline must
    name the gateway; that is the whole point of the block."""
    _tree(bzs, tmp_path, monkeypatch, {
        "shadow_health.json": timedelta(hours=2, minutes=6),
        "gateway_state.json": timedelta(days=23),
        "account_state.json": timedelta(minutes=1),
    })
    got = bzs._organs(NOW)
    assert got["worst"] == "DEAD"
    assert got["down"] == ["gateway_state.json"]
    assert "gateway_state.json" in got["headline"], (
        "the headline does not name the dead organ, so the reader still has to already suspect "
        "it -- which is precisely how twenty-three days went unnoticed")
    assert got["rows"][0]["organ"] == "gateway_state.json", "worst is not first"
    assert _by_organ(got)["shadow_health.json"] == "LATE"


def test_three_weeks_and_forty_six_minutes_do_not_print_the_same_word(
        bzs, tmp_path, monkeypatch) -> None:
    """The ladder. `per_report` graded both STALE, which rendered the one number that mattered as
    the routine case."""
    _tree(bzs, tmp_path, monkeypatch, {
        "shadow_health.json": timedelta(minutes=46),
        "gateway_state.json": timedelta(days=23),
    })
    v = _by_organ(bzs._organs(NOW))
    assert v["gateway_state.json"] == "DEAD" and v["shadow_health.json"] == "LATE"
    assert v["gateway_state.json"] != v["shadow_health.json"]


def test_the_age_is_rendered_for_a_human(bzs, tmp_path, monkeypatch) -> None:
    """`2049285` is not a number anyone reads as three weeks, and salience is the entire job."""
    _tree(bzs, tmp_path, monkeypatch, {"gateway_state.json": timedelta(days=23)})
    (row,) = [r for r in bzs._organs(NOW)["rows"] if r["organ"] == "gateway_state.json"]
    assert row["age"] == "23d"
    assert bzs._age_human(7591) == "2.1h" and bzs._age_human(2760) == "46m"
    assert bzs._age_human(None) == "?"


# --------------------------------------------------------------------------- the ladder itself
@pytest.mark.parametrize(("age", "expect"), [
    (timedelta(minutes=5), "LIVE"),
    (timedelta(minutes=44), "LIVE"),
    (timedelta(minutes=46), "LATE"),
    (timedelta(hours=5), "LATE"),
    (timedelta(hours=7), "STALE"),
    (timedelta(hours=23), "STALE"),
    (timedelta(hours=25), "DEAD"),
    (timedelta(days=23), "DEAD"),
])
def test_every_rung_is_reachable(bzs, tmp_path, monkeypatch, age, expect) -> None:
    """A ladder whose top rung no age reaches is a ladder with one rung and a longer name."""
    _tree(bzs, tmp_path, monkeypatch, {"gateway_state.json": age})
    assert _by_organ(bzs._organs(NOW))["gateway_state.json"] == expect


def test_a_dead_organ_says_what_makes_it_dead_rather_than_only_that_it_is(
        bzs, tmp_path, monkeypatch) -> None:
    _tree(bzs, tmp_path, monkeypatch, {"gateway_state.json": timedelta(days=23)})
    (row,) = [r for r in bzs._organs(NOW)["rows"] if r["organ"] == "gateway_state.json"]
    assert "at least daily" in row["why"] and "not running" in row["why"], (
        "the row states a verdict but not its basis; a reader cannot tell a dead producer from "
        "a threshold someone set too tight")


# ------------------------------------------------------- absence, and the watchdog's own verdict
def test_an_organ_with_no_clock_ranks_above_a_stale_one(bzs, tmp_path, monkeypatch) -> None:
    """An organ nobody can SEE could be any age, including dead since before anyone looked."""
    _tree(bzs, tmp_path, monkeypatch, {
        "gateway_state.json": timedelta(hours=8),      # STALE, measured
        "regime_state.json": None,                     # no clock at all
    })
    rows = bzs._organs(NOW)["rows"]
    order = [r["organ"] for r in rows]
    assert _by_organ(bzs._organs(NOW))["regime_state.json"] == "UNMEASURED"
    assert order.index("regime_state.json") < order.index("gateway_state.json")


def test_nothing_reported_is_not_reported_as_health(bzs, tmp_path, monkeypatch) -> None:
    """The failure this block exists to expose must not be able to render as a clean board."""
    _tree(bzs, tmp_path, monkeypatch, {})
    got = bzs._organs(NOW)
    assert got["worst"] != "LIVE"
    assert "LIVE" not in got["headline"]


def test_a_failing_task_is_surfaced_even_though_its_artifact_is_fresh(
        bzs, tmp_path, monkeypatch) -> None:
    """A DIFFERENT KIND OF EVIDENCE. A task can run, error, and leave yesterday's file in place:
    fresh by every age-based reading on this board, and broken."""
    _tree(bzs, tmp_path, monkeypatch,
          {"shadow_health.json": timedelta(minutes=3)},
          failing=("MT5-MoatRecorder",))
    got = bzs._organs(NOW)
    assert "MT5-MoatRecorder" in got["down"]
    assert got["worst"] == "FAILING"
    assert _by_organ(got)["shadow_health.json"] == "LIVE", "the fresh organ was mislabelled"


def test_a_healthy_desk_says_so_without_inventing_a_problem(bzs, tmp_path, monkeypatch) -> None:
    """EVERY tracked artifact fresh, not merely the two a test happened to write. Leaving three
    of the five out makes the block read UNMEASURED -- correctly, since absence is never a pass,
    which is why this fixture names them all rather than the ones the assertion is about."""
    _tree(bzs, tmp_path, monkeypatch,
          {rel.rsplit("/", 1)[-1]: timedelta(minutes=3 + i)
           for i, (rel, _) in enumerate(bzs.BOX_REPORTS)})
    got = bzs._organs(NOW)
    assert got["worst"] == "LIVE" and got["down"] == []
    assert "no organ down" in got["headline"]


# ------------------------------------------------------------------ and it must reach the page
def test_the_organ_block_reaches_the_published_payload(bzs, tmp_path, monkeypatch) -> None:
    """Every outage on this board so far has been a correct reading nobody carried. So this
    drives the real builder, not the helper."""
    _tree(bzs, tmp_path, monkeypatch, {
        "shadow_health.json": timedelta(hours=2),
        "gateway_state.json": timedelta(days=23),
    })
    monkeypatch.setattr(bzs, "_mt5_snapshot", lambda: {})
    organs = bzs.build()["organs"]
    assert organs["worst"] == "DEAD" and organs["down"] == ["gateway_state.json"]
