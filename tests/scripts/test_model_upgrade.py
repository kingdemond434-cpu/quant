"""Invariants for the automatic model-upgrade path.

An upgrade engine that can silently DOWNGRADE the desk is worse than no upgrade engine: the
panel's whole value is uncorrelated flagship review, and the brain chain's ordering encodes
which billing pool each organ draws from. Every assertion here is a guard against a specific
way an "upgrade" could quietly make the desk worse -- lab diversity collapsing, a context
window shrinking, a free/weak tier sneaking in, anthropic entering the panel that exists to be
uncorrelated with Claude, or a chain being reordered onto the wrong credit pool.
"""

from __future__ import annotations

from scripts.brain_model_upgrade import (
    best_candidate,
    newer,
    parse_model,
    rewrite_text,
    upgrade_chain,
)
from scripts.model_upgrade import candidates, invariants_hold, parse_rows, regressed_seats
from scripts.seats import resolve_ids


def _m(mid, created, ctx=1_000_000):
    return {"id": mid, "created": created, "context_length": ctx}


# ---------------------------------------------------------------- panel candidate selection
def test_candidate_must_be_same_lab():
    """Cross-lab swaps can duplicate a lineage and destroy uncorrelated consensus."""
    cat = [_m("x-ai/grok-4.3", 100), _m("openai/gpt-9", 900)]
    assert candidates(cat, "x-ai/grok-4.3") == []


def test_candidate_must_be_newer():
    cat = [_m("x-ai/grok-4.3", 500), _m("x-ai/grok-4.1", 100)]
    assert candidates(cat, "x-ai/grok-4.3") == []


def test_newer_same_lab_flagship_is_a_candidate():
    cat = [_m("x-ai/grok-4.3", 500), _m("x-ai/grok-5", 900)]
    assert candidates(cat, "x-ai/grok-4.3") == ["x-ai/grok-5"]


def test_context_regression_is_never_a_candidate():
    """Full-coverage review was bought with >=1M-context seats; a smaller window re-breaks it."""
    cat = [_m("x-ai/grok-4.3", 500, 1_000_000), _m("x-ai/grok-5", 900, 260_000)]
    assert candidates(cat, "x-ai/grok-4.3") == []


def test_weak_and_free_tiers_are_excluded():
    """`:free` rate-limits and returns blanks -- a silent seat loss inside a consensus panel."""
    cat = [_m("x-ai/grok-4.3", 500), _m("x-ai/grok-5-mini", 900),
           _m("x-ai/grok-5-flash", 950), _m("x-ai/grok-5:free", 990)]
    assert candidates(cat, "x-ai/grok-4.3") == []


def test_dead_incumbent_yields_no_candidates():
    """A dead seat is refresh_panel_roster's job; upgrading is only for a LIVE incumbent."""
    cat = [_m("x-ai/grok-5", 900)]
    assert candidates(cat, "x-ai/grok-4.3") == []


def test_candidates_are_newest_first_and_capped():
    cat = [_m("x-ai/grok-4.3", 100), _m("x-ai/grok-5", 500),
           _m("x-ai/grok-6", 900), _m("x-ai/grok-7", 950)]
    got = candidates(cat, "x-ai/grok-4.3", limit=2)
    assert got == ["x-ai/grok-7", "x-ai/grok-6"]


# ---------------------------------------------------------------- roster invariants
def test_invariants_reject_lab_collapse():
    old = ["x-ai/grok-4.3", "openai/gpt-5"]
    new = ["openai/gpt-6", "openai/gpt-5"]              # two seats, but one lab
    ok, why = invariants_hold(old, new)
    assert not ok and "diversity" in why


def test_invariants_reject_seat_loss():
    ok, why = invariants_hold(["a/x", "b/y"], ["a/x"])
    assert not ok and "seat count" in why


def test_invariants_reject_anthropic_entering_the_panel():
    """The panel audits a Claude brain; an anthropic seat trades away its only real property."""
    ok, why = invariants_hold(["x-ai/grok-4.3"], ["anthropic/claude-opus-5"])
    assert not ok and "excluded lab" in why


def test_invariants_accept_a_clean_same_lab_upgrade():
    ok, _ = invariants_hold(["x-ai/grok-4.3", "openai/gpt-5"],
                            ["x-ai/grok-5", "openai/gpt-5"])
    assert ok


def test_invariants_reject_a_duplicated_seat():
    """13 entries holding 12 unique models is 13 seats on paper and 12 reviewers in reality.

    Caught in review: the roster runs TWO openai and TWO google seats, so both siblings were
    offered their lab's single newest model. List length and lab count both looked unchanged.
    """
    ok, why = invariants_hold(["a/one", "a/two", "b/three"], ["a/new", "a/new", "b/three"])
    assert not ok and "distinct models" in why


# ---------------------------------------------------------------- two seats sharing one lab
def test_sibling_seats_never_collapse_onto_one_model():
    cat = [_m("a/one", 100), _m("a/two", 100), _m("a/new", 900)]
    seated = {"a/one", "a/two"}
    picks: dict[str, str] = {}
    for inc in ("a/one", "a/two"):
        for c in candidates(cat, inc, taken=seated):
            if c in picks.values():                 # adoption-time dedupe
                continue
            picks[inc] = c
            break
    assert picks == {"a/one": "a/new"}              # only ONE seat may take the single new model
    assert len(set(picks.values())) == len(picks)


def test_sibling_seat_is_not_starved_when_two_upgrades_exist():
    """The first fix over-reserved a whole shortlist and starved the sibling. Both must upgrade."""
    cat = [_m("a/one", 100), _m("a/two", 100), _m("a/new-x", 900), _m("a/new-y", 880)]
    seated = {"a/one", "a/two"}
    picks: dict[str, str] = {}
    for inc in ("a/one", "a/two"):
        for c in candidates(cat, inc, taken=seated):
            if c in picks.values():
                continue
            picks[inc] = c
            break
    assert picks == {"a/one": "a/new-x", "a/two": "a/new-y"}


def test_a_seated_model_is_never_offered_as_an_upgrade():
    """Proposing a model the roster already holds is a duplicate by another name."""
    cat = [_m("a/one", 100), _m("a/two", 900)]
    assert candidates(cat, "a/one", taken={"a/one", "a/two"}) == []


# ---------------------------------------------------------------- gauntlet parsing / rollback
def test_parse_rows_accepts_the_desk_format_and_rejects_prose():
    text = ("Here are my thoughts on the matter.\n"
            "HIGH | libs/execution/staging.py | retry can resend a filled order\n"
            "MEDIUM | config/risk.yaml | default is 10x the documented value\n")
    rows = parse_rows(text)
    assert len(rows) == 2
    assert rows[0][1] == "libs/execution/staging.py"


def test_parse_rows_returns_nothing_for_unparseable_answers():
    """The gpt-5.6-terra-pro failure class: fluent prose, zero machine-readable rows."""
    assert parse_rows("I reviewed the code and found two concerning issues worth discussing.") == []


def test_regressed_seat_rolls_back_to_its_predecessor():
    state = {"promoted": {"x-ai/grok-5": "x-ai/grok-4.3"}}
    assert regressed_seats(state, {"x-ai/grok-5": 4}) == [("x-ai/grok-5", "x-ai/grok-4.3")]


def test_healthy_promotion_is_not_rolled_back():
    state = {"promoted": {"x-ai/grok-5": "x-ai/grok-4.3"}}
    assert regressed_seats(state, {"x-ai/grok-5": 1}) == []


def test_hand_chosen_seat_is_never_auto_reverted():
    """Only promotions this engine made are eligible -- the principal's picks are his."""
    assert regressed_seats({"promoted": {}}, {"openai/gpt-5": 9}) == []


# ---------------------------------------------------------------- seat resolution (organs)
def test_present_preferred_seats_pass_through_unchanged():
    """No-op on a stable roster: organs must behave identically until an upgrade happens."""
    want = ["a/one", "b/two"]
    got, subs = resolve_ids(want, ["a/one", "b/two", "c/three"])
    assert got == want and subs == []


def test_upgraded_away_seat_is_substituted_same_lab_first():
    got, subs = resolve_ids(["a/one"], ["a/one-v2", "z/other"])
    assert got == ["a/one-v2"]
    assert subs == [("a/one", "a/one-v2")]


def test_substitution_preserves_distinct_labs():
    got, _ = resolve_ids(["a/one", "b/two"], ["a/one", "a/spare", "c/three"])
    assert got == ["a/one", "c/three"]                   # never two seats from lab 'a'


def test_unreplaceable_seat_is_reported_not_silently_dropped():
    """The exact defect this layer exists to close: a lost seat must be loud."""
    got, subs = resolve_ids(["a/one", "b/two"], ["a/one"])
    assert got == ["a/one"]
    assert subs == [("b/two", None)]


# ---------------------------------------------------------------- brain chain (Claude organs)
def test_parse_model_reads_family_and_version():
    assert parse_model("claude-opus-4-8") == ("opus", (4, 8))
    assert parse_model("claude-opus-5") == ("opus", (5,))
    assert parse_model("claude-haiku-4-5-20251001") == ("haiku", (4, 5))
    assert parse_model("gpt-5") is None


def test_version_ordering_beats_string_ordering():
    """String sort puts 'claude-opus-4-8' after 'claude-opus-5'; version tuples must not."""
    assert newer("claude-opus-5", "claude-opus-4-8")
    assert not newer("claude-opus-4-8", "claude-opus-5")


def test_cross_family_is_never_an_upgrade():
    """A family hop silently moves the slot onto a different billing pool."""
    assert not newer("claude-fable-5", "claude-opus-4-8")
    assert best_candidate(["claude-fable-9"], "claude-opus-5") is None


def test_best_candidate_picks_the_highest_version():
    avail = ["claude-opus-5", "claude-opus-5-1", "claude-opus-4-8"]
    assert best_candidate(avail, "claude-opus-4-8") == "claude-opus-5-1"


def test_incumbent_is_demoted_not_deleted():
    """Retention IS the rollback path: a starved promotion falls through to known-good."""
    chain = ["claude-opus-5", "claude-opus-4-8", "claude-fable-5"]
    got = upgrade_chain(chain, [], {"claude-opus-5": "claude-opus-6"})
    assert got == ["claude-opus-6", "claude-opus-5", "claude-opus-4-8", "claude-fable-5"]


def test_chain_order_is_never_reordered():
    """brain_env leads with opus (Max seat) and ends with fable (metered pool) on purpose."""
    chain = ["claude-opus-5", "claude-opus-4-8", "claude-fable-5"]
    got = upgrade_chain(chain, [], {"claude-fable-5": "claude-fable-6"})
    assert got[0] == "claude-opus-5"                     # Max-seat model still leads
    assert got[-2:] == ["claude-fable-6", "claude-fable-5"]


def test_miner_inverted_chain_keeps_its_own_ordering():
    """run_frontier_miner deliberately puts fable FIRST (resumable rotation). Respect it."""
    chain = ["claude-fable-5", "claude-opus-5", "claude-opus-4-8"]
    got = upgrade_chain(chain, [], {"claude-fable-5": "claude-fable-6"})
    assert got[0] == "claude-fable-6"
    assert got[1] == "claude-fable-5"


def test_rewrite_touches_only_real_assignments():
    """Prose and comments naming a model id must not be rewritten into config."""
    body = ('# we run claude-opus-5 because the Max seat is cheaper than fable\n'
            'export _BRAIN_MODEL_CHAIN="claude-opus-5 claude-opus-4-8"\n'
            'export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-opus-5}"  # primary\n')
    out, changes = rewrite_text(body, {"claude-opus-5": "claude-opus-6"})
    assert out.splitlines()[0] == body.splitlines()[0]           # comment untouched
    assert '_BRAIN_MODEL_CHAIN="claude-opus-6 claude-opus-5 claude-opus-4-8"' in out
    assert 'ANTHROPIC_MODEL:-claude-opus-6}' in out
    assert len(changes) == 2


def test_rewrite_is_a_noop_without_approved_upgrades():
    body = 'export _BRAIN_MODEL_CHAIN="claude-opus-5 claude-opus-4-8"\n'
    out, changes = rewrite_text(body, {})
    assert out == body and changes == []
