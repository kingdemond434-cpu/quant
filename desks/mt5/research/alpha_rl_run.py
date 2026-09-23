"""G4 -- THE RL ALPHA SEARCH, ACTUALLY RUN. A learner nothing runs has learned nothing.

`libs/research/alpha_rl.py` has been complete for days: a tabular Q-learner over the
alpha-construction MDP, a replay buffer, an epsilon floor, and a reward that is the allocator's
own marginal dE[log W]. Its Tier-1 row said `SEQUENTIAL CONTROL NOW EXISTS AND IS MEASURED;
NOTHING RUNS IT` -- which is III.16 exactly: built is not done, and a module with no clock and no
artifact is a claim the desk cannot cash.

This is the runner. It does one thing: load the reward from the allocator's artifact, roll
episodes under a wall-clock budget, and publish what was learned AND what was refused.

THE REFUSALS ARE THE POINT, NOT THE FOOTNOTE. `BookReward.from_artifact` returns UNMEASURED when
there is no allocator artifact or it carries no finite marginal, and `run_episodes` then runs
NOTHING -- no transition, no update, an empty Q table. An episode whose completed spec the book
has never valued is DISCARDED WHOLE rather than scored zero, because zero asserts that admitting
it adds nothing and nobody measured that. Both counts are published here, so a reader can tell a
run that learned from a real book from one that had no book to learn against. A ranking earned
against a fabrication is indistinguishable from a real one unless the artifact says so.

WHAT THE RANKING IS. The MDP's state is a PREFIX of construction decisions, so a reward earned by
one completed spec moves the value of a decision several layers above it. The published table is
therefore not "good specs" -- it is which DECISION, at which layer, the book's own marginals have
paid for. `match_depth` rides on every reward and is counted, so the share of learning that came
from an exact (symbol, family, window) match rather than a family-level mean is visible rather
than assumed.

IT PROPOSES AND DOES NOT PROMOTE. Nothing here writes a sleeve, a certificate or a docket row.
The consumer is the proposer budget: `hourly_discovery._weight` and `daily_cycle.arm_weight`
already set per-proposer `budget_s` from EVOLUTION.json, and this artifact is the second arm's
evidence in the same shape.

Artifact: desks/mt5/reports/ALPHA_RL.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import set_aside as sa  # noqa: E402

OUT = DESK / "reports" / "ALPHA_RL.json"

#: Wall-clock budget for one pass. The hourly cycle bills every leg, and a search that cannot say
#: when it will stop cannot be given a slot; `run_episodes` honours this and reports how many of
#: the requested episodes it actually reached.
DEFAULT_BUDGET_S = 45.0

#: Episodes requested. The budget, not this, is what usually binds -- it is an upper bound so a
#: fast host does not spin forever on a table that stopped moving.
DEFAULT_EPISODES = 4000

#: How many ranked prefixes to publish. The table is large and its tail is noise; the head is
#: what a proposer budget can act on.
TOP_N = 40


def run(*, episodes: int = DEFAULT_EPISODES, budget_s: float = DEFAULT_BUDGET_S,
        seed: int = 20260913) -> dict[str, Any]:
    now = datetime.now(UTC)
    try:
        import numpy as np

        from libs.research.alpha_rl import (
            AlphaMDP,
            BookReward,
            EpsilonGreedy,
            QLearner,
            ReplayBuffer,
            run_episodes,
        )
    except Exception as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURABLE",
                "why": f"alpha_rl is not importable ({type(exc).__name__}: {str(exc)[:160]})"}

    reward = BookReward.from_artifact()
    try:
        mdp = AlphaMDP.from_registries()
    except Exception as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURABLE",
                "why": f"the MDP could not be built from the registries ({type(exc).__name__}: "
                       f"{str(exc)[:160]})",
                "reward_basis": reward.basis, "reward_why": reward.why}

    rng = np.random.default_rng(seed)
    learner = QLearner()
    res = run_episodes(mdp, learner, reward, episodes=episodes, rng=rng,
                       buffer=ReplayBuffer(), epsilon=EpsilonGreedy(),
                       budget_s=budget_s, basis=reward.basis, basis_why=reward.why)

    # THE RANKING IS OVER DECISIONS, NOT OVER SPECS. Each row is a prefix and its learned value,
    # so a reader sees which choice at which layer the book paid for -- which is the thing a
    # proposer budget can actually act on.
    ranked: list[dict[str, Any]] = []
    q = getattr(learner, "q", {}) or {}
    for state_action, value in q.items():
        try:
            state, action = state_action
        except Exception:
            continue
        if not isinstance(value, (int, float)):
            continue
        prefix = [str(x) for x in state] if isinstance(state, tuple) else [str(state)]
        ranked.append({"prefix": prefix, "decision": str(action),
                       "value": round(float(value), 8),
                       "layer": len(state) if isinstance(state, tuple) else None})
    ranked.sort(key=lambda r: -r["value"])

    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"),
        "status": "MEASURED" if res.reward_basis == "MEASURED" and res.updates else "UNMEASURED",
        # WHAT THE RUN WAS ALLOWED TO LEARN FROM, first, because everything below is worthless
        # without it. An UNMEASURED basis means the episodes were not run at all.
        "reward_basis": res.reward_basis,
        "reward_why": res.reward_why,
        "reward_detail": res.reward_detail,
        "episodes_requested": episodes,
        "episodes_run": res.episodes,
        "budget_s": budget_s,
        # THE REFUSAL COUNTS. `unpriced` is episodes the book has never valued at any coordinate,
        # discarded whole rather than scored zero; `truncated` is the budget or the horizon
        # ending a rollout. A run with a large unpriced share learned from a narrow slice of the
        # book and the ranking below should be read that way.
        "rewarded": res.rewarded,
        "unpriced": res.unpriced,
        "truncated": res.truncated,
        "updates": res.updates,
        "replayed": res.replayed,
        "states_visited": res.states_visited,
        "epsilon_final": round(float(res.epsilon_final), 4),
        # How much of the learning came from an exact (symbol, family, window) match rather than
        # a family-level mean. A table learned mostly at `family` depth is a coarser claim.
        "match_depths": dict(res.match_depths),
        "n_ranked": len(ranked),
        # TOP_N IS A PUBLICATION BUDGET, NOT A SCREEN (LAWS 7). The tail is still ranked and
        # still counted in `n_ranked`; what it may not be is dropped without a name, so the
        # remainder is recorded in reports/SET_ASIDE_LEDGER.json with the ordering key.
        "top": sa.take(ranked, TOP_N, organ="alpha_rl_run", stage="ranked_prefixes",
                       ordering="rank order from run_episodes (value of the decision prefix)"),
        "rule": ("the state is a PREFIX of construction decisions, so a reward earned by one "
                 "completed spec moves the value of a decision several layers above it -- this "
                 "ranks DECISIONS the book's marginals paid for, not specs"),
        "consumer": ("proposer budget_s in hourly_discovery._weight and daily_cycle.arm_weight, "
                     "the same shape EVOLUTION.json already feeds"),
        "authority": ("ZERO. Nothing here writes a sleeve, a certificate or a docket row; the ten "
                      "gates and a forward clock decide what runs, exactly as for anything else"),
    }
    if res.reward_basis != "MEASURED":
        doc["why"] = ("no episode was run: " + (res.reward_why or "the reward is UNMEASURED") +
                      " -- an empty table is the honest output, not a zero-valued one")
    return doc


def write(doc: dict[str, Any], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--episodes", type=int, default=DEFAULT_EPISODES)
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = run(episodes=args.episodes, budget_s=args.budget_s)
    write(doc, args.out)
    if doc["status"] in ("UNMEASURABLE", "UNMEASURED"):
        print(f"alpha_rl: {doc['status']} -- {str(doc.get('why') or doc.get('reward_why'))[:180]}")
    else:
        print(f"alpha_rl: {doc['episodes_run']} episode(s), {doc['rewarded']} rewarded, "
              f"{doc['unpriced']} unpriced, {doc['updates']} update(s), "
              f"{doc['states_visited']} state(s), depths {doc['match_depths']}")
        for r in doc["top"][:5]:
            print(f"   {r['value']:+.6f}  layer {r['layer']}  {r['decision']}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
