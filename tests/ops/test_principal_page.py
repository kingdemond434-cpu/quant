"""The principal page must never lose a message it did not write.

Locks the 2026-07-29 finding: `run_external_panel`'s bare `write_text` deleted a pending Tier-3
YES/NO ask (GAP #71, the gate blocking the whole discovery pipeline) when it paged an unrelated
OpenRouter credit notice. The register went on recording that ask as "paged, awaiting a ruling".
"""

from __future__ import annotations

from pathlib import Path

from libs.ops import principal_page as pp

_ASK = (
    "URGENT 2026-07-29: Tier-3 YES/NO -- flip pbo/rc to per-candidate gates?\n"
    "  - 420/420 rejected by two campaign constants; fix built, 13 tests green.\n"
    "  - Thresholds numerically unchanged; production flip NOT self-applied.\n"
)


def test_preserves_an_unrelated_pending_ask(tmp_path: Path) -> None:
    """THE REGRESSION: the exact loss that happened on the live desk.

    CONTRACT UPDATED 2026-07-31. The original assertion ("pager reads line 1 only" so the
    purchase notice must OWN line 1) locked in the very ordering the desk ruled a FAILURE on
    07-30, when an unrelated PURCHASE DECISION prepended above two Tier-3 asks put both rulings
    below the fold and the principal was paged housekeeping instead (max_audit POSITION FIX).
    The ruled priority: a fresh URGENT block outranks any non-urgent page; the daily reminder
    re-sends the standing Tier-3 ask, which is the correct thing for line 1 to carry. The
    non-urgent message must still LAND and survive -- that half of the 07-29 lock is unchanged."""
    p = tmp_path / "PRINCIPAL_ACTION.md"
    p.write_text(_ASK, "utf-8")
    out = pp.page(
        "PURCHASE DECISION: OpenRouter credits exhausted (balance $-0.59).",
        marker="PURCHASE DECISION:", path=p)
    assert out.splitlines()[0].startswith("URGENT")      # Tier-3 ask keeps the top
    assert "PURCHASE DECISION:" in out                   # the notice LANDED below it
    assert "Tier-3 YES/NO" in out                        # the ask SURVIVED
    assert "13 tests green" in out                       # including its indented detail


def test_repeat_page_replaces_its_own_block_not_stacking(tmp_path: Path) -> None:
    p = tmp_path / "PRINCIPAL_ACTION.md"
    p.write_text(_ASK, "utf-8")
    for bal in ("-0.59", "-1.20", "-3.00"):
        out = pp.page(f"PURCHASE DECISION: balance ${bal}.",
                      marker="PURCHASE DECISION:", path=p)
    assert out.count("PURCHASE DECISION:") == 1          # updated in place
    assert "-3.00" in out and "-0.59" not in out         # newest wins
    assert "Tier-3 YES/NO" in out                        # still preserved after 3 rounds


def test_two_different_organs_coexist(tmp_path: Path) -> None:
    p = tmp_path / "PRINCIPAL_ACTION.md"
    pp.page("BUDGET DECISION: envelope would be exceeded.",
            marker="BUDGET DECISION:", path=p)
    out = pp.page("PURCHASE DECISION: credits exhausted.",
                  marker="PURCHASE DECISION:", path=p)
    assert "BUDGET DECISION:" in out and "PURCHASE DECISION:" in out
    assert out.splitlines()[0].startswith("PURCHASE DECISION:")   # most recent owns line 1


def test_writes_to_a_fresh_file(tmp_path: Path) -> None:
    p = tmp_path / "nested" / "PRINCIPAL_ACTION.md"
    out = pp.page("PURCHASE DECISION: credits exhausted.", marker="PURCHASE DECISION:", path=p)
    assert out.strip() == "PURCHASE DECISION: credits exhausted."
