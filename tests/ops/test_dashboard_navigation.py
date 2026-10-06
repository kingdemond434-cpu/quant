"""ONE CANONICAL PUBLIC DASHBOARD; THE PROTECTED SURVEILLANCE VIEW SHARES ITS STATE.

WHAT THIS TEST USED TO GUARD, and why the guard changed rather than went away. `web/index.html`
was the landing page and every link in its nav was a `#fragment` inside itself, so
`web/research.html` -- which carried the Stage-B shadow clocks -- was reachable only by typing
its filename. A page nobody can navigate to is a page nobody reads.

The desk had THREE dashboards by 2026-09-06: index.html (the retired Zenith build, 55KB),
research.html (22KB), and desk.html. Three views of one desk is worse than one: they disagree,
each is stale in a different way, and "which one is right" becomes a question the operator has to
answer before reading any number. So the answer to the navigation problem is no longer "link them
together" -- it is that there is only one page to be on.

index.html and research.html are now REDIRECTS rather than deletions. dash.quanttt.xyz and every
bookmark, tunnel and nginx root that already points at them keeps working and lands on the real
dashboard; deleting them would have turned a live URL into a 404 for no gain.
"""
from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parent.parent.parent / "web"
CANONICAL = "desk.html"
PROTECTED_SURVEILLANCE = "dashboard.html"


def test_the_canonical_dashboard_exists() -> None:
    page = WEB / CANONICAL
    assert page.is_file(), "the one canonical dashboard is gone"
    assert len(page.read_text("utf-8")) > 5_000, "desk.html is a stub, not a dashboard"


#: The pages that are REDIRECTS to the canonical dashboard, pinned by name. A glob of "everything
#: else" was the old form, and it went red the day two full dashboards were deliberately served
#: beside desk.html -- the test then asserted a rule the desk had already decided against.
REDIRECTS: tuple[str, ...] = ("index.html", "research.html")

#: Full dashboards that are SERVED ON PURPOSE and are therefore not redirects. Each carries its
#: reason; a page earns a place here by naming who serves it, never by being inconvenient to the
#: glob below. Kept as full pages by the coordinator's decision of 2026-09-30 (live's behaviour).
SERVED_FULL_PAGES: dict[str, str] = {
    "dashboard.html": ("the box's own page: MT5-DeskDashboard serves it on the trading box "
                       "(install_desk_dashboard_task.ps1 binds web\\dashboard.html) and "
                       "hourly_cycle:desk_dashboard_state feeds it DESK_DASHBOARD_STATE.json"),
    "desk_pro.html": ("the live desk view reading the same desk_state.json as desk.html; landed "
                      "as a full page in bcbec41f0 and kept as one"),
}


def test_every_other_page_redirects_to_it() -> None:
    """THE ONE THAT MATTERS. No page may present a second, disagreeing view of the desk -- except
    the served full dashboards named above, each with its reason.

    Every html page under web/ must be exactly one of: the canonical page, a pinned redirect, or
    a named served full page. A NEW page that is neither fails here, so the exception list cannot
    grow by accident."""
    pages = {p.name for p in WEB.glob("*.html")}
    assert pages, "nothing to check -- the glob is wrong and this test proves nothing"
    unclassified = pages - {CANONICAL} - set(REDIRECTS) - set(SERVED_FULL_PAGES)
    assert not unclassified, (
        f"{sorted(unclassified)} is neither a redirect to {CANONICAL} nor a named served "
        "dashboard; make it a redirect, or add it to SERVED_FULL_PAGES with who serves it")
    assert all(SERVED_FULL_PAGES.values()), "every served full page must carry its reason"
    assert not set(REDIRECTS) & set(SERVED_FULL_PAGES), "a page cannot be both"
    for name in REDIRECTS:
        p = WEB / name
        assert p.is_file(), f"{name} is gone: a live URL that redirected is now a 404"
        src = p.read_text("utf-8")
        if p.name == PROTECTED_SURVEILLANCE:
            # This separately served read-only surveillance view has a token gate and more
            # provenance detail. It is not a second source of truth or a trading control.
            assert "desk_state.json" in src and "read-only" in src
            assert "desk_dashboard_state" in src
            continue
        assert CANONICAL in src, f"{p.name} does not point at {CANONICAL}"
        assert 'http-equiv="refresh"' in src and "location.replace" in src, (
            f"{p.name} mentions {CANONICAL} but does not actually redirect to it -- a second "
            "dashboard that merely links to the first is still a second dashboard, and the "
            "operator still has to decide which number to believe")
        assert len(src) < 4_000, (
            f"{p.name} is {len(src)} bytes; a redirect is a redirect, and anything this large "
            "is a dashboard wearing one as a hat")
    for name in SERVED_FULL_PAGES:
        p = WEB / name
        assert p.is_file(), f"{name} is named as a served dashboard but does not exist"
        src = p.read_text("utf-8")
        assert "location.replace" not in src and 'http-equiv="refresh"' not in src, (
            f"{name} now redirects; move it from SERVED_FULL_PAGES to REDIRECTS")
        assert len(src) > 5_000, f"{name} is a stub, not the full dashboard it is listed as"


def test_the_canonical_page_reads_the_published_state() -> None:
    """A dashboard that cannot reach desk_state.json shows nothing, however good it looks."""
    src = (WEB / CANONICAL).read_text("utf-8")
    assert "desk_state.json" in src
    assert "build_zentech_state.py" in src, (
        "the page no longer names its producer; when it goes stale the reader has no thread to "
        "pull, which is exactly how a ten-day-old board went unnoticed")


def test_the_canonical_page_says_when_the_box_last_reported() -> None:
    """The single most important line on a dashboard for a desk holding live capital.

    A board showing ten-day-old numbers and one showing live numbers are pixel-identical; only
    the age distinguishes them, and for ten days the age was the one thing not on screen.
    """
    src = (WEB / CANONICAL).read_text("utf-8")
    for token in ("SILENT", "REPORTING", "box"):
        assert token in src, f"the dashboard never renders {token!r}; box liveness is invisible"
