"""run_external_panel pages via libs.ops.principal_page (wired 2026-08-05).

The module's own docstring records the origin: on 2026-07-29 the panel's bare
`Path("data/PRINCIPAL_ACTION.md").write_text(...)` clobbered a pending Tier-3 YES/NO ask
(GAP #71, the #1 register item) with a credits notice. The append-safe helper was built from that
incident and the panel was never migrated to it. These tests pin the wiring and the exact
data-loss scenario it prevents.
"""
from __future__ import annotations

from pathlib import Path

from libs.ops.principal_page import page

_SRC = Path(__file__).resolve().parents[2] / "scripts" / "run_external_panel.py"


def test_panel_never_bare_writes_the_principal_page():
    src = _SRC.read_text("utf-8")
    assert 'PRINCIPAL_ACTION.md").write_text' not in src, (
        "run_external_panel writes the principal page bare again -- the 2026-07-29 clobber "
        "deleted a pending Tier-3 ask; page via libs.ops.principal_page.page instead")
    assert "_principal_page(" in src, "the append-safe pager import was removed"
    assert 'marker="BUDGET DECISION:"' in src
    assert 'marker="PURCHASE DECISION:"' in src


def test_credits_page_preserves_a_pending_tier3_ask(tmp_path):
    """The literal 2026-07-29 incident, replayed against the wired call shape."""
    p = tmp_path / "PRINCIPAL_ACTION.md"
    p.write_text("URGENT: Tier-3 YES/NO -- pbo/rc campaign-constant gate fix (GAP #71).\n",
                 "utf-8")
    out = page("PURCHASE DECISION: OpenRouter credits exhausted (balance $0.12, a panel run "
               "needs ~$2.00).", marker="PURCHASE DECISION:", path=p)
    assert out.lstrip().startswith("URGENT: Tier-3 YES/NO"), \
        "a budget notice took line 1 from a pending Tier-3 ask"
    assert "PURCHASE DECISION:" in out
    assert "GAP #71" in out, "the pending ask was destroyed by an unrelated organ's notice"


def test_repeat_budget_pages_replace_their_own_block_not_stack(tmp_path):
    p = tmp_path / "PRINCIPAL_ACTION.md"
    page("BUDGET DECISION: MTD $90.00 would exceed the $120/mo envelope.",
         marker="BUDGET DECISION:", path=p)
    out = page("BUDGET DECISION: MTD $95.00 would exceed the $120/mo envelope.",
               marker="BUDGET DECISION:", path=p)
    assert out.count("BUDGET DECISION:") == 1, "repeat pages must update in place"
    assert "$95.00" in out and "$90.00" not in out
