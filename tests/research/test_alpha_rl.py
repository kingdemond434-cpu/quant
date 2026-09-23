"""Sequential control over the alpha-construction MDP: what a PREFIX is worth.

WHY THE DISTINCTION IS NOT VOCABULARY, and why these tests are built around it. The desk already
had a bandit over finished populations, and G4 was recorded as landed on that. A bandit sees a
completed cell and one number: asked "was choosing metals at step 2 a good idea?", it has no
representation in which the question can be posed. A sequential learner holds Q(partial spec,
next decision), so a reward earned by one completion moves the value of a decision three layers
above it -- which is the entire reason search gets cheaper.

So the load-bearing tests here are: credit reaches a PREFIX from completions beneath it; the
action set at layer 3 DEPENDS on the decision taken at layer 0 (a product of independent axes is
not an MDP); and every refusal that stops the agent learning a fabrication -- an UNMEASURED
reward runs no episodes at all, an UNPRICED completion is discarded whole rather than scored
zero, and exploration has a floor that can never be set to zero.

The universe is checked too, because the principal's standing order makes it load-bearing: every
action set comes from the desk's own Fusion registries, so there is no code path here through
which a crypto-exchange-native universe could be reached.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "desks" / "mt5")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import alpha_rl as rl  # noqa: E402


def _rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


class _Toy:
    """A two-layer MDP whose reward depends ONLY on the first decision.

    The point of the fixture: if credit assignment works, the agent must learn to prefer the
    good first action even though the reward is only ever observed at a terminal state two
    decisions later, and even though every second-layer action is equally worthless.
    """

    LAYERS = ("first", "second")

    def actions(self, state):
        if len(state) == 0:
            return (("first", "good"), ("first", "bad"))
        if len(state) == 1:
            return tuple(("second", f"s{i}") for i in range(4))
        return ()

    def is_terminal(self, state) -> bool:
        return len(state) >= 2

    def spec(self, state) -> dict:
        return dict(state)


def _toy_reward(state):
    return (1.0 if ("first", "good") in state else 0.0), "toy"


# -------------------------------------------------------------- credit reaches the prefix
def test_a_reward_earned_at_a_leaf_moves_the_value_of_the_decision_two_layers_above_it():
    """THE WHOLE DIFFERENCE FROM A BANDIT. Nothing here ever scores the first decision
    directly; its value has to arrive from the completions beneath it."""
    learner = rl.QLearner()
    out = rl.run_episodes(_Toy(), learner, _toy_reward, episodes=400, rng=_rng(),
                          basis=rl.MEASURED, basis_why="toy")
    assert out.rewarded > 0 and out.updates > 0
    q_good = learner.q.get(((), ("first", "good")))
    q_bad = learner.q.get(((), ("first", "bad")))
    assert q_good is not None and q_bad is not None, learner.q
    assert q_good > q_bad, (
        f"the root decision was not valued from its completions: good {q_good} vs bad {q_bad}; "
        f"this is bandit behaviour, not sequential control")


def test_the_agent_ends_up_choosing_the_prefix_that_paid():
    learner = rl.QLearner()
    rl.run_episodes(_Toy(), learner, _toy_reward, episodes=400, rng=_rng(1),
                    basis=rl.MEASURED, basis_why="toy")
    best = learner.greedy((), _Toy().actions(()))
    assert best == ("first", "good"), best


# -------------------------------------------------------------------------- the refusals
def test_an_unmeasured_reward_runs_no_episodes_and_leaves_the_table_empty():
    """THE REFUSAL IS AT THE TOP OF THE LOOP AND IT IS TOTAL. Rolling out with a placeholder
    reward would produce a confident ranking of a fabrication, and a reader of the artifact
    could not tell it from a ranking earned against a real book."""
    learner = rl.QLearner()
    out = rl.run_episodes(_Toy(), learner, _toy_reward, episodes=200, rng=_rng(),
                          basis=rl.UNMEASURED, basis_why="no allocator artifact")
    assert out.episodes == 0 and out.updates == 0 and out.rewarded == 0
    assert not learner.q, "the Q table was written from an unmeasured reward"
    assert out.reward_basis == rl.UNMEASURED and out.reward_why


def test_an_unpriced_completion_is_discarded_whole_and_never_scored_zero():
    """A zero reward is a CLAIM -- 'this adds nothing to the book' -- and it is a claim nobody
    measured. The episode's transitions must never reach the table."""
    learner = rl.QLearner()
    out = rl.run_episodes(_Toy(), learner, lambda s: (None, "unpriced"), episodes=50,
                          rng=_rng(), basis=rl.MEASURED, basis_why="book present")
    assert out.unpriced == out.episodes > 0
    assert out.rewarded == 0 and out.updates == 0
    assert not learner.q


def test_exploration_has_a_floor_and_a_zero_floor_is_refused():
    """An agent that stops exploring converges on the current book, which is the one region
    where new alpha is worth least."""
    with pytest.raises(ValueError, match="epsilon floor must be > 0"):
        rl.EpsilonGreedy(floor=0.0)
    eps = rl.EpsilonGreedy(start=0.9, decay=0.5, floor=0.05)
    assert eps.value(0) == pytest.approx(0.9)
    assert eps.value(1000) == pytest.approx(0.05), "the floor did not hold at long horizons"


def test_an_unbounded_replay_buffer_is_refused():
    with pytest.raises(ValueError, match="unbounded buffer is refused"):
        rl.ReplayBuffer(capacity=0)


def test_the_replay_ring_drops_the_oldest_and_never_grows_past_its_capacity():
    buf = rl.ReplayBuffer(capacity=3)
    for i in range(10):
        buf.add(rl.Transition(state=(), action=("a", str(i)), reward=float(i),
                              next_state=(), terminal=True))
    assert len(buf) == 3
    kept = {t.action[1] for t in buf.rows()}
    assert kept == {"7", "8", "9"}, kept


def test_sampling_is_driven_by_a_passed_generator_and_is_reproducible():
    """Never by module-level randomness: a buffer that samples from a hidden source makes a run
    impossible to replay."""
    buf = rl.ReplayBuffer(capacity=50)
    for i in range(50):
        buf.add(rl.Transition(state=(), action=("a", str(i)), reward=float(i),
                              next_state=(), terminal=True))
    a = [t.action for t in buf.sample(8, _rng(3))]
    b = [t.action for t in buf.sample(8, _rng(3))]
    assert a == b and len(a) == 8


# ------------------------------------------------------ the MDP is the desk's own registries
def test_the_action_set_at_a_later_layer_depends_on_the_decision_taken_earlier():
    """WHAT MAKES IT A SEQUENTIAL PROBLEM. A product of independent axes would offer the same
    timeframes whatever family was chosen, and then a prefix would carry no information."""
    mdp = rl.AlphaMDP.from_registries(symbols=["XAUUSD", "EURUSD"])
    roots = mdp.actions(())
    assert len(roots) > 1, roots
    seen = set()
    for fam in roots[:12]:
        state = (fam,)
        while not mdp.is_terminal(state) and len(state) < 4:
            acts = mdp.actions(state)
            if not acts:
                break
            if acts[0][0] == "timeframe":
                seen.add(tuple(a[1] for a in acts))
                break
            state = (*state, acts[0])
    assert len(seen) > 1, (
        "every family offered the same timeframe domain; the layers are independent axes and "
        "the prefix carries no information")


def test_every_action_comes_from_a_desk_registry_and_names_which_one():
    mdp = rl.AlphaMDP.from_registries(symbols=["XAUUSD"])
    for axis in ("families", "symbols", "sessions", "timeframes", "parameters"):
        assert mdp.inputs.get(axis), f"{axis} does not say where its actions came from"


def test_the_symbol_actions_are_fusion_symbols_and_nothing_else():
    """THE PRINCIPAL'S STANDING ORDER, IN ARITHMETIC (MT5 universe mandate, 2026-08-18). The
    only symbol source is the desk's own Fusion table, so a crypto-exchange-native name is not
    an action and cannot be selected, scored or emitted."""
    uni, why = rl.desk_universe()
    assert uni and "universe.json" in why
    mdp = rl.AlphaMDP.from_registries()
    symbol_actions = set()
    for fam in mdp.actions(())[:3]:
        symbol_actions |= {a[1] for a in mdp.actions((fam,))}
    assert symbol_actions <= set(uni), sorted(symbol_actions - set(uni))[:10]


def test_a_completed_episode_is_a_spec_the_desk_could_actually_run():
    mdp = rl.AlphaMDP.from_registries(symbols=["XAUUSD", "EURUSD", "USDJPY"])
    out = rl.run_episodes(mdp, rl.QLearner(), lambda s: (0.0012, "fixture"), episodes=25,
                          rng=_rng(), basis=rl.MEASURED, basis_why="fixture")
    assert out.completed
    uni = set(rl.desk_universe()[0])
    fams = set(rl.orthogonal_families()[0])
    for ep in out.completed:
        spec = ep.spec
        assert spec["symbol"] in uni and spec["family"] in fams, spec
        assert spec["timeframe"] and isinstance(spec.get("params"), dict)


# -------------------------------------------------------------------- the reward's provenance
def test_a_missing_allocator_artifact_reads_unmeasured_and_says_which_file(tmp_path):
    reward = rl.BookReward.from_artifact(tmp_path / "nothing.json")
    assert reward.basis == rl.UNMEASURED
    assert "no allocator artifact" in reward.why and "contributes no update" in reward.why


def test_an_artifact_with_no_finite_marginal_is_unmeasured_not_zero(tmp_path):
    p = tmp_path / "pf_allocation.json"
    p.write_text(json.dumps({"marginal_delta_elog": {"a.b.c": None}}), "utf-8")
    reward = rl.BookReward.from_artifact(p)
    assert reward.basis == rl.UNMEASURED
    assert "no finite marginal" in reward.why and "nothing is learned" in reward.why


def test_a_coordinate_the_book_has_never_valued_is_unpriced_and_not_zero(tmp_path):
    """The three match depths and the refusal beneath them, driven through the DESK'S OWN
    sleeve-name parser rather than a spelling invented here -- `_sleeve_axes` is deliberately
    `portfolio_gap.sleeve_axes` when the desk is importable, so a test that hardcoded a format
    would pass while the reward priced nothing on the box."""
    name = "XAUUSD_carry_london"
    axes = rl._sleeve_axes(name)
    sym, fam, win = axes["symbol"], axes["family"], axes["window"]
    p = tmp_path / "pf_allocation.json"
    p.write_text(json.dumps({"marginal_delta_elog": {name: 0.002}}), "utf-8")
    reward = rl.BookReward.from_artifact(p)
    assert reward.basis == rl.MEASURED and reward.n_priced == 1

    exact, depth = reward((), {"symbol": sym, "family": fam, "session": win})
    assert exact == pytest.approx(0.002) and depth == "exact"

    other, depth = reward((), {"symbol": sym, "family": fam, "session": "a_window_never_traded"})
    assert other == pytest.approx(0.002) and depth == "symbol_family", (
        "the book holds this instrument in this family; that is a measured number about a real "
        "coordinate and must be used before falling through")

    value, why = reward((), {"symbol": "NZDCAD", "family": "unheard_of", "session": "asia"})
    assert value is None, (value, why)
    assert "never valued this coordinate" in why


def test_the_reward_knows_which_coordinates_the_book_already_funds():
    """A coordinate the book HOLDS is not a research candidate; the agent must be able to tell."""
    reward = rl.BookReward(basis=rl.MEASURED, funded={("XAUUSD", "carry", "london")})
    assert reward.is_funded({"symbol": "XAUUSD", "family": "carry", "session": "london"})
    assert not reward.is_funded({"symbol": "XAUUSD", "family": "carry", "session": "asia"})
