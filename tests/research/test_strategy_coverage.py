"""R0200 -- coverage is the count of DISTINCT FAMILIES, and an imported finding may suggest but
never authorise."""
from __future__ import annotations

import json

from scripts.run_strategy_coverage import (
    FAMILIES,
    THIN_BELOW,
    _corpus,
    coverage,
    discretionary_candidates,
    import_to_playbook,
)

_REPO = __import__("pathlib").Path(__file__).resolve().parent.parent.parent


def _grave(tmp_path, names):
    (tmp_path / "docs/research").mkdir(parents=True, exist_ok=True)
    rows = "\n".join(f"| {n} (some description) | metrics | reason | notes" for n in names)
    (tmp_path / "docs/graveyard.md").write_text("| name | why |\n|---|---|\n" + rows, "utf-8")


def test_the_real_graveyard_parses_nearly_all_of_it():
    """REGRESSION PIN. The first parser anchored on a closing pipe, but most rows continue with
    a parenthetical ("kama_squeeze (TTM squeeze + KAMA...)"), so it silently read 11 of 42 rows
    -- and a coverage organ reading a quarter of the record reports NEVER-HUNTED for families
    the desk has genuinely worked, which is worse than not reporting at all."""
    names = [n for n, o in _corpus(_REPO) if o == "graveyard"]
    assert len(names) >= 40, f"parsed only {len(names)} graveyard rows"
    # a spot-check across three different families, each with a parenthetical in the real file
    assert "kama_squeeze" in names
    assert "hyperliquid_trader_skill_persistence" in names
    assert "era_ta_indicator_stack_crypto" in names


def test_twelve_candidates_from_one_family_is_not_coverage(tmp_path):
    """The whole thesis: correlated candidates die together, so the desk learns roughly one
    thing. Coverage counts families, never candidates."""
    _grave(tmp_path, [f"funding_variant_{i}" for i in range(12)])
    c = coverage(tmp_path)
    assert c["families"]["CARRY-FUNDING"]["state"] == "HUNTED"
    assert c["n_hunted"] == 1                       # twelve candidates, ONE family
    assert c["status"] == "UNCOVERED"
    assert c["n_candidates_seen"] == 12             # and the candidate count is not the metric


def test_a_single_candidate_leaves_a_family_thin_not_hunted(tmp_path):
    """One test is an anecdote and two a coincidence."""
    _grave(tmp_path, ["some_grid_ladder_bot"])
    f = coverage(tmp_path)["families"]["MARKET-MAKING-EXECUTION"]
    assert f["state"] == "THIN" and f["n_tested"] < THIN_BELOW
    assert "NOT covered" in f["why"]


def test_never_hunted_is_reported_as_a_finding(tmp_path):
    _grave(tmp_path, ["funding_a", "funding_b", "funding_c"])
    c = coverage(tmp_path)
    assert "STATISTICAL-ARBITRAGE" in c["unhunted"]
    assert "finding, not an omission" in c["families"]["STATISTICAL-ARBITRAGE"]["why"]
    # and the organ points the NEXT dig at an unhunted family, never at a worked one
    assert c["next_family"] in c["unhunted"]
    assert "not deepen" in c["never_narrow"]


# ---- the discretionary import, and the asymmetry that makes it safe ---------------------------

def test_only_families_the_sleeve_can_act_on_are_routed():
    """A carry or on-chain finding is real research the sleeve cannot express; routing it would
    be noise in the one brief that has to stay sharp."""
    fams = {c["family"] for c in discretionary_candidates(_REPO)}
    assert fams <= {k for k, v in FAMILIES.items() if v["discretionary"]}
    assert "CARRY-FUNDING" not in fams and "ONCHAIN-FLOW" not in fams
    assert "TREND-AND-STRUCTURE" in fams          # the sleeve's own family


def test_imports_enter_at_the_back_of_the_queue_never_authorised(tmp_path):
    """An outside finding may SUGGEST a method change; only the sleeve's own closed trades may
    authorise one. An import that skipped run_trade_review's N_SUPPORT queue would let an
    untested external claim rewrite the money path silently."""
    _grave(tmp_path, ["tftrailbreakout", "kama_squeeze", "trend_regime_gated"])
    (tmp_path / "data").mkdir(exist_ok=True)
    out = import_to_playbook(tmp_path)
    assert out["n_filed"] >= 1
    pb = json.loads((tmp_path / "data/trading_playbook.json").read_text("utf-8"))
    imported = [lv for lv in pb["lessons"] if lv.get("imported_from")]
    assert imported
    for lv in imported:
        assert lv["status"] == "PROVISIONAL"
        assert lv["support"] == 0                 # zero, so it cannot be one trade from the brief
        assert "SUGGESTS ONLY" in lv["authority"]
        assert "NOT from a closed trade" in lv["origin"]


def test_import_is_idempotent(tmp_path):
    _grave(tmp_path, ["tftrailbreakout", "kama_squeeze"])
    (tmp_path / "data").mkdir(exist_ok=True)
    first = import_to_playbook(tmp_path)["n_filed"]
    assert first >= 1
    assert import_to_playbook(tmp_path)["n_filed"] == 0      # re-running files nothing new


def test_imported_lessons_never_reach_the_trading_brief(tmp_path):
    """The end-to-end safety property, asserted against the REAL consumer rather than inferred."""
    from scripts.run_conviction_trader import _playbook_brief
    _grave(tmp_path, ["tftrailbreakout", "kama_squeeze"])
    (tmp_path / "data").mkdir(exist_ok=True)
    import_to_playbook(tmp_path)
    brief = _playbook_brief(tmp_path)
    assert "no SUPPORTED lessons" in brief
    assert "trend" not in brief.lower()          # the imported claim itself is nowhere in it


def test_an_unreadable_corpus_reports_unreadable_not_never_hunted(tmp_path):
    """With no corpus every family reads NEVER-HUNTED -- this organ's loudest verdict -- produced
    by a missing file rather than a real gap, and the families alone cannot tell the two apart.
    The build-standard fence caught the original `except: pass` here, correctly."""
    c = coverage(tmp_path)                       # no docs/graveyard.md at all
    assert c["status"] == "UNREADABLE"
    assert c["read_errors"] and "graveyard unreadable" in c["read_errors"][0]
    assert "NOT a coverage finding" in c["detail"]
