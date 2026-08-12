"""The dashboard had no idea the shadow pipeline existed.

MEASURED 2026-08-12, after the principal asked why no candidates appear on the dashboard:
index.html and research.html load thirty-odd JSON feeds between them and NOT ONE is a shadow or
candidate feed. `web/paper_sleeve_forward.json` was already sitting in the served directory and no
page had ever fetched it. Ten clocks in shadow and twenty-six queued survivors had never had a
view -- read-without-writer inverted, written and served and read by nobody.

These tests pin the feed's honesty rather than its prettiness: it must never truncate the thing it
exists to show, must never be able to change what it displays, and must carry the age of every
number so a fossil cannot be rendered as current fact.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "publish_pipeline", _REPO / "scripts/publish_pipeline.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------ it must not touch anything
def test_the_publisher_never_runs_the_organ_it_reports_on(mod) -> None:
    """THE BUG THIS FILE CAUGHT IN ITS OWN FIRST DRAFT. The publisher invoked
    run_paper_sleeve_spawner as a subprocess so the queue would be fresh. That organ SPAWNS
    sleeves, edits the roster and rewrites the queue, and it is scheduled under its own flock --
    so the publisher became a second, unlocked writer on files another organ owns. That is the
    R0048 shape this desk already has a fence for.

    A dashboard must never be able to change what it is displaying.

    CHECKED ON THE AST, NOT ON THE TEXT. The first version of this assertion grepped the source
    for "subprocess" and failed on the docstring above, which EXPLAINS the bug -- the same
    string-marker mistake that made seat_preflight match the word "seats" in a prose comment.
    A module is allowed to describe what it must not do.
    """
    import ast
    tree = ast.parse((_REPO / "scripts/publish_pipeline.py").read_text("utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    for forbidden in ("subprocess", "os"):
        assert forbidden not in imported, f"{forbidden} is imported -- this must stay a pure read"


def test_it_writes_only_under_web(mod) -> None:
    """A publisher that writes into data/ is an organ wearing a publisher's name."""
    import ast
    assert mod.OUT.startswith("web/")
    tree = ast.parse((_REPO / "scripts/publish_pipeline.py").read_text("utf-8"))
    writes = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr in ("write_text", "write_bytes", "mkdir", "unlink", "replace")]
    assert {n.func.attr for n in writes} <= {"write_text", "mkdir"}, (
        "the publisher may create its own directory and write its one feed, nothing else")
    assert sum(1 for n in writes if n.func.attr == "write_text") == 1, (
        "exactly one write, and it is the feed")


# ------------------------------------------------------------------ the funnel is honest
def test_every_stage_carries_its_own_denominator(mod, tmp_path: Path) -> None:
    """A funnel that only shows survivors cannot distinguish 'nothing survived' from 'nothing was
    tried', and those call for opposite responses."""
    d = mod.build(root=tmp_path)
    stages = [s["stage"] for s in d["funnel"]]
    assert stages == ["screened", "candidates", "sleeve_records", "in_shadow", "queued",
                      "accruing", "resolved"]
    for s in d["funnel"]:
        assert s["why"], f"{s['stage']} publishes a number with no explanation"


def test_the_strongest_verdict_of_all_is_a_candidate(mod) -> None:
    """THE BUG THIS FILE CAUGHT IN ITS OWN FIRST DRAFT, and it was the worst possible one.

    The publisher hardcoded a POSITIVE candidate list -- UNDERPOWERED, UNRATED, WEAK -- which
    silently excluded SCREEN-INTERESTING. axis_screen is explicit that SCREEN-INTERESTING is "the
    ONLY verdict that starts a forward clock". So the first genuine survivor this desk ever
    produced would have rendered on the dashboard as NOT A CANDIDATE, on the one view built to
    show the principal that progress was happening.
    """
    assert mod.is_candidate("SCREEN-INTERESTING")


def test_weak_and_underpowered_stay_candidates(mod) -> None:
    """L1.49 WEAK IS NOT DEAD. An underpowered screen has not measured anything yet, and a view
    that hid those trials would report a desk with no candidates when it has 84."""
    for v in ("SCREEN-UNDERPOWERED", "SCREEN-UNRATED", "SCREEN-WEAK"):
        assert mod.is_candidate(v), v


def test_a_broken_measurement_is_not_a_candidate(mod) -> None:
    """Look-ahead and timing artifacts name a BROKEN number, not a weak one. Consistency of an
    artifact is not evidence."""
    for bad in ("NOT-A-CANDIDATE", "TIMING-ARTIFACT", "SUSPECT-LOOKAHEAD", "NOT-READABLE-HERE"):
        assert not mod.is_candidate(bad), bad


def test_the_dashboard_and_the_spawner_share_one_definition(mod) -> None:
    """ONE QUANTITY, ONE DEFINITION. slot_registry exists because the Holm m was counted three
    different ways by three files and the loosest copy won. A dashboard keeping its own idea of
    what a candidate is would be that failure again, on the view the principal trusts to tell them
    whether anything is happening."""
    from libs.research.paper_sleeves import NON_ADMISSIBLE_PREFIXES
    assert mod.NON_ADMISSIBLE_PREFIXES is NON_ADMISSIBLE_PREFIXES
    src = (_REPO / "scripts/publish_pipeline.py").read_text("utf-8")
    assert "CANDIDATE_VERDICTS = (" not in src, "the hardcoded positive list must not come back"


def test_an_empty_box_reports_unmeasured_never_an_empty_pipeline(mod, tmp_path) -> None:
    """UNMEASURED IS NEVER ZERO. A container with no artifacts must not render as a desk that
    found nothing -- that is the reading that gets a working pipeline declared dead."""
    d = mod.build(root=tmp_path)
    assert d["authority"]["mode"] == "UNMEASURED"
    assert "has not run on this box" in d["authority"]["why"]
    assert all(v is None for v in d["source_ages_h"].values())


# ------------------------------------------------------------------ freshness
def test_every_source_publishes_its_age(mod, tmp_path: Path) -> None:
    """A dashboard rendering a fortnight-old queue as current fact is the 2026-08-05 conversion
    failure with a nicer font. The ages travel with the counts."""
    d = mod.build(root=tmp_path)
    assert set(d["source_ages_h"]) >= {"forward", "authority", "gate", "spawn_queue"}
    assert "read the ages, not just the counts" in d["freshness_warning"]


def test_the_law_is_stated_in_the_feed_not_only_in_the_code(mod, tmp_path) -> None:
    """The page shows a full slot table next to a queue of 26. Without the law beside it that
    reads as rejection, when it is a concurrency limit."""
    d = mod.build(root=tmp_path)
    assert "ZERO promotion authority" in d["law"]
    assert "CONCURRENCY limit" in d["law"]


# ------------------------------------------------------------------ the live desk
def test_it_publishes_the_real_pipeline(mod) -> None:
    d = mod.build(root=_REPO)
    by = {s["stage"]: s["n"] for s in d["funnel"]}
    assert by["screened"] > 0, "no screened trial is visible at all"
    assert by["candidates"] <= by["screened"]
    assert by["in_shadow"] <= by["sleeve_records"]
    assert len(d["screened"]) == by["screened"], "the trial list must not be truncated"
    assert len(d["queue"]) == by["queued"], "the queue must not be truncated"


def test_no_list_is_capped_to_a_top_n(mod) -> None:
    """The whole point is that the principal can see ALL of them. Truncating recreates the
    situation this was built to fix."""
    body = (_REPO / "scripts/publish_pipeline.py").read_text("utf-8").split('"""', 2)[2]
    assert "[:10]" not in body and "[:20]" not in body and "[:50]" not in body


# ------------------------------------------------------------------ the page
def test_the_page_exists_and_reads_the_feed() -> None:
    html = (_REPO / "web/pipeline.html").read_text("utf-8")
    assert "pipeline.json" in html
    for section in ("funnel", "sleeves", "queue", "screened", "auth"):
        assert f'id="{section}"' in html, section


def test_the_page_is_reachable_from_the_pages_that_already_exist() -> None:
    """A page nobody can navigate to is a page nobody reads -- the same defect one level up."""
    for page in ("web/index.html", "web/research.html"):
        assert "pipeline.html" in (_REPO / page).read_text("utf-8"), page


def test_a_missing_feed_renders_as_unmeasured_not_as_an_empty_pipeline() -> None:
    """If the fetch fails the page must say so. Rendering empty tables would tell the principal
    the desk has no candidates, which is the one wrong answer available."""
    html = (_REPO / "web/pipeline.html").read_text("utf-8")
    assert "FEED UNAVAILABLE" in html
    assert "UNMEASURED" in html and "never an empty pipeline" in html


def test_the_page_shows_why_each_clock_is_not_breathing() -> None:
    """Ten clocks reading NO-EVIDENCE is only actionable if the page says WHY -- a stale container,
    a dead producer and a fixed window call for three different responses."""
    html = (_REPO / "web/pipeline.html").read_text("utf-8")
    for state in ("SOURCE_STALE_HERE", "SOURCE_FROZEN", "PRODUCER_UNSCHEDULED"):
        assert state in html, state
    assert "FIX:" in html, "a health verdict with no repair is a complaint"


# ------------------------------------------------------------------ the wiring
def test_the_publisher_is_scheduled_often_enough_to_be_current() -> None:
    """The chain it reports on moves seven times between 06:40 and 12:15, and the only other
    writer of web/ runs once at 06:04. Daily publication would show yesterday's pipeline every
    time the principal looked."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    lines = [ln for ln in man.splitlines()
             if "publish_pipeline.py" in ln and ln[:1].isdigit()]
    assert lines, "the pipeline feed is on no schedule"
    assert any(ln.split()[1] == "*" for ln in lines), (
        "publishing less often than hourly leaves the dashboard behind the chain it reports on")
