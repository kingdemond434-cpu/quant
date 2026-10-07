"""THREE SEATS THAT PRODUCED HUNDREDS OF ARTIFACTS AND THEN STOPPED, EACH FOR ITS OWN REASON.

Measured on the trading box 2026-09-24. All three logged `LEG_DONE outcome=ok` every hour while
producing nothing, which is why none of them read as broken:

  event_response_atlas   258 artifacts, then 15 consecutive clean runs donating nothing. It
                         applied its OWN Bonferroni threshold as a donation filter, and that
                         threshold is a function of how many cells it tested -- so it RISES with
                         generation. At 636 cells it was t=3.9486 and the strongest cell in the
                         whole atlas was t=-3.617. The door did not narrow, it shut.
                         Measured: 279 of 300 published cells CLEAR COST, 0 clear Bonferroni.

  research_tree          138 artifacts, then silence. `_donate` read `doc["frontier"]`, which is
                         `frontier[:30]` -- a PUBLICATION cut. Measured: the published 30 held
                         0 nodes with a spec, while the full frontier held 3,292 donatable ones.

  alpha_periodic_table   its report went 47h stale while the leg ran hourly and exited 0, because
                         the module's `__main__` was a print-only demo that never called `main()`.

None of these is a threshold change, and none of them makes the desk trade differently: the ten
gates, the fixed 7x DSR multiplier and every bar in gate_spec.yaml are untouched. What changes is
how much reaches them.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ------------------------------------------------------------------ event_response_atlas
def test_the_atlas_no_longer_carries_a_bar_of_its_own() -> None:
    """RESEARCH.md 6d: no screen may apply a threshold of its own IN EITHER DIRECTION. A screen
    sorts and reports; the ten gates decide. This is the third such bar the desk has had to
    remove, after a sqrt(2 ln N) screen and an n_trials override inside a gate (both 2026-08-26).
    """
    src = (_DESK / "research" / "event_response_atlas.py").read_text(encoding="utf-8")
    line = next(ln for ln in src.splitlines() if ln.strip().startswith("clearing = ["))
    assert "clears_bonferroni" not in line, (
        "the donation filter must not consult clears_bonferroni -- that bar RISES with the number "
        "of cells tested, so it closes itself as the atlas broadens")
    assert 'r["verdict"] == "CLEARS_COST"' in line


def test_the_bonferroni_reading_is_still_measured_and_published() -> None:
    """Removing its AUTHORITY is not the same as removing the measurement. A reader still wants
    to know how a cell stands against the multiple-testing reference."""
    from research import event_response_atlas as era

    assert callable(era.bonferroni_t)
    assert era.bonferroni_t(636) > 3.9
    src = (_DESK / "research" / "event_response_atlas.py").read_text(encoding="utf-8")
    assert 'row["clears_bonferroni"] = ' in src, "every row still carries the reading"
    assert '"threshold_t"' in src, "the pass still publishes the threshold it computed"


def test_the_only_remaining_screen_is_economic() -> None:
    """Cost is the desk's own spread, not a statistical bar: a cell whose |mean| is inside the
    spread cannot be traded at all, which is a different claim from 'not significant enough'."""
    src = (_DESK / "research" / "event_response_atlas.py").read_text(encoding="utf-8")
    body = src.split("def donate_clearing", 1)[1].split("def ", 1)[0]
    for bar in ("threshold", "bonferroni", "alpha", "p_value", "pvalue"):
        assert f"if {bar}" not in body, f"a {bar} bar reappeared inside the donation path"


# ------------------------------------------------------------------------- research_tree
def test_the_donation_walks_the_whole_frontier_not_the_published_slice() -> None:
    """A readability cap must never decide what reaches the judge."""
    from research import research_tree as rt

    published = [{"id": "root|mechanism:x|a", "kind": "portfolio_residual_variant", "label": "r",
                  "question": "q", "spec": None, "posterior_value": 0.1,
                  "info_gain_nats": 0.1, "cost_cells": 1.0, "gain_per_cell": 0.9}] * 30
    below_the_cut = [{"id": "root|mechanism:overnight_gap_decay|b", "kind": "execution_variant",
                      "label": "exec:trigger0.5", "question": "q2",
                      "spec": {"symbol": "EURUSD", "trigger": 0.5}, "posterior_value": 0.01,
                      "info_gain_nats": 0.01, "cost_cells": 1.0, "gain_per_cell": 0.01}]
    doc = {"frontier": published, "evidence": {"n_trials": 100}}

    # The old behaviour, reproduced exactly: reading only the published slice finds nothing.
    assert rt._donate(doc)["donated"] == 0

    # ...and the full frontier is what it must actually read.
    sent: dict[str, object] = {}

    def _fake_donate(source: str, cands: list[dict], tests_run: int) -> Path:
        sent["source"], sent["cands"] = source, cands
        return Path("donated.json")

    import research.proposer_common as pc
    real, pc.donate = pc.donate, _fake_donate
    try:
        out = rt._donate(doc, published + below_the_cut)
    finally:
        pc.donate = real

    assert out["donated"] == 1, out
    assert sent["source"] == "research_tree"
    assert sent["cands"][0]["symbol"] == "EURUSD"          # type: ignore[index]
    assert sent["cands"][0]["family"] == "joint_genome"    # type: ignore[index]


def test_the_full_frontier_is_never_written_to_the_report() -> None:
    """6,000+ nodes belong to the donation, not to a file a human opens. The published slice must
    stay exactly the size it was, or this fix trades one defect for a 40 MB report."""
    src = (_DESK / "research" / "research_tree.py").read_text(encoding="utf-8")
    assert '"frontier": frontier[:30],' in src, "the PUBLISHED slice is unchanged"
    assert 'doc.pop("_full_frontier", None)' in src, "the full frontier is popped before writing"


def test_the_remaining_cap_is_a_batch_budget_and_is_labelled_as_one() -> None:
    """A cap that is a compute budget must say so, or the next reader takes it for a belief about
    where edges stop (RESEARCH.md 6c-bis)."""
    src = (_DESK / "research" / "research_tree.py").read_text(encoding="utf-8")
    doc = src.split("def _donate", 1)[1].split('"""', 2)[1]
    assert "BATCH BUDGET" in doc


# ------------------------------------------------------------------- alpha_periodic_table
def test_the_module_entry_point_produces_rather_than_prints() -> None:
    """`hourly_cycle` runs this file as a subprocess every hour. What it ran was an exploratory
    print block; `main()` -- the only path that writes the report -- was dead code. Exit 0, no
    write, forever."""
    src = (_DESK / "side_channels" / "alpha_periodic_table.py").read_text(encoding="utf-8")
    tail = src.split('if __name__ == "__main__":', 1)[1]
    assert "raise SystemExit(main())" in tail, (
        "the module's __main__ must reach main(), which is the only caller of run()")
    assert tail.index('if "--demo"') < tail.index("raise SystemExit(main())"), (
        "the demo must be gated behind an explicit flag, never the default path")


def test_the_demo_is_kept_rather_than_deleted() -> None:
    """Deleting it only tempts the next author to re-add it in front of main() again."""
    src = (_DESK / "side_channels" / "alpha_periodic_table.py").read_text(encoding="utf-8")
    assert "--demo" in src and "get_research_targets()" in src
