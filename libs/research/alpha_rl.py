"""SEQUENTIAL control over the alpha-construction MDP -- the value of a PARTIAL specification.

WHAT WAS ACTUALLY MISSING (external audit, verified on this tree 2026-09-09). A grep for
`q_learning|policy_gradient|actor_critic|replay_buffer|ppo|epsilon_greedy` across `libs/` and
`desks/` returned ONE hit, in a scraper. The desk has a GFlowNet-style sampler
(`libs/research/gflownet.py`), a Thompson/UCB bandit over finished populations
(`libs/research/bandit.py`), and a genetic search -- and the ledger recorded G4 as landed on the
strength of ordering whole POPULATIONS by realised growth. That is bandit-style credit assignment
over completed candidates. It is not sequential control, and the difference is not vocabulary.

    A bandit sees a FINISHED cell and one number. Asked "was choosing metals at step 2 a good
    idea?", it has no representation in which the question can be posed: `XAUUSD.carry.london`
    and `XAUUSD.vol_transition.asia` are two unrelated arms that happen to share a prefix.

    A sequential learner holds Q(partial spec, next decision). Choosing `carry` is an ACTION
    taken in the root state, and every completion beneath it updates its value. The agent
    therefore learns what a PREFIX is worth before any of its completions is screened -- which
    is the entire reason search gets cheaper: it stops paying to complete branches whose prefix
    has never paid.

THE MDP, and every one of its action sets comes from a registry this desk already owns. Nothing
is re-listed here, because a re-listed vocabulary is a search over a universe the desk cannot
trade:

    layer 0  family      mt5desk.families_orthogonal.ORTHOGONAL_FAMILIES   (34 on 2026-09-09)
    layer 1  symbol      desks/mt5/data/universe/universe.json, the ONE registry file
                         `mt5desk.universe_registry` documents itself as the sole writer of
    layer 2  session     libs.research_os.dsl.SESSIONS, on the broker's own UTC+3 clock
    layer 3  timeframe   families_orthogonal.timeframe_domain(family) -- so the action set at
                         layer 3 DEPENDS on the decision taken at layer 0, which is what makes
                         this a sequential decision problem and not a product of independent axes
    layer 4+ parameter   the chosen family function's OWN signature defaults, scaled by
                         PARAM_MULTIPLIERS. A family that changes a default moves the grid with
                         it; there is no second copy of the number to drift.

THE UNIVERSE IS MT5/FUSION BY CONSTRUCTION, not by a filter that could be forgotten. The only
symbol source is the desk's own Fusion symbol table, and the only mechanism source is the desk's
own family registry. There is no code path here through which a crypto-exchange-native universe
(Binance/Bybit/OKX/Hyperliquid) could be reached: a name that is not in Fusion's table is not an
action, so it cannot be selected, scored or emitted.

REWARD IS MARGINAL PORTFOLIO UTILITY, AND IT IS REFUSED WHEN IT IS NOT MEASURED.
The reward for a completed spec is the marginal dE[log W] it would add to the CURRENT book, read
from the allocator's own artifact `desks/mt5/reports/pf_allocation.json`. Not Sharpe -- a Sharpe
says nothing about what heat a candidate earns beside what the desk already holds. Not survival
-- a cell that lives is not a cell that pays.

    WHAT THAT ARTIFACT'S KEYS ACTUALLY ARE, because conflating them is how this desk once came
    to believe it had an admission criterion (pf_allocator.py:3395-3401, its own words):
      * `marginal_delta_elog`  is the GRADIENT of the robust objective at the SOLVED book -- the
        value of each funded sleeve's LAST unit of heat. It is the key this module was told to
        read and it is read, but it is a property of sleeves the book HOLDS.
      * `admission.candidates[*].delta_elogw_per_day` is the marginal of ADMITTING a sleeve the
        book does not hold -- it re-solves the whole book around the candidate.
    Where the artifact carries the admission block, THAT is preferred, because it is the
    quantity the reward is defined as. `reward_basis_detail` on every report says which was used.

    WHEN THERE IS NO ARTIFACT THE EPISODE RETURNS `UNMEASURED` AND CONTRIBUTES NO UPDATE. Not a
    zero, not a prior, not a Sharpe standing in. A zero reward is a CLAIM ("this adds nothing to
    the book") and it is a claim nobody measured; an agent trained on it would learn a confident
    ranking of a fabrication, which is strictly worse than no agent at all -- the desk would then
    spend screen budget in an order it believed was evidence. `run_episodes` refuses: with an
    UNMEASURED book the Q table is left EMPTY and the report says so.

    A COMPLETED SPEC WHOSE COORDINATE THE BOOK HAS NEVER PRICED IS `UNPRICED`, and that episode
    is discarded whole -- no transition enters the buffer, no update is applied, and the count is
    reported. The agent may only learn from coordinates the allocator has actually valued.

WHY THE EPSILON FLOOR NEVER DECAYS TO ZERO. An epsilon-greedy agent whose exploration decays to
zero converges onto the region its reward function scores highest -- and this reward function is
read off the CURRENT BOOK. The book is precisely the one region where new alpha is worth least:
its coordinates are already funded, already crowded by the desk's own heat, and a marginal
dE[log W] measured there is the value of the last unit of heat in a sleeve that already exists.
A converged agent would therefore spend the whole screen budget re-proposing the desk's own
positions. The floor (`EPSILON_FLOOR`, 0.10) is what keeps a fixed share of every run pointed at
coordinates the book has never priced. It is not a tuning knob to be annealed away; a floor of
zero is refused at construction.

DETERMINISTIC GIVEN A SEED. One `numpy.random.default_rng` drives every choice, every replay
draw and every tie-break; the Q table is a plain dict iterated in sorted order everywhere it is
read out. Two runs over one transition set produce byte-identical Q tables.

NOTHING HERE HAS AUTHORITY. This orders where the desk spends its screen budget. It sizes
nothing, it certifies nothing, it moves no gate, threshold, floor or law, and the specs it
prefers still go through `proposer_common.donate` into the miner-candidate compiler and the same
ten gates as everything else. A high Q buys a screen and nothing more.
"""
from __future__ import annotations

import inspect
import json
import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple, Protocol

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: The allocator's own artifact. The ONLY source of reward in this module.
PF_ALLOCATION = DESK / "reports" / "pf_allocation.json"
#: The one registry file `mt5desk.universe_registry` documents itself as the sole writer of.
UNIVERSE_JSON = DESK / "data" / "universe" / "universe.json"

#: A session a family cannot express. A family whose signature has no hour parameter has no way
#: to say "London" -- handing it a session anyway would manufacture two specs that compile to one
#: identical cell, and the desk's identity law would then see a collision it did not cause.
SESSION_ANY = "any"

#: The grid around a family's OWN default, as multiples of it. Half, itself, double: a coarse
#: bracket, because this module chooses WHERE to spend a screen, and the screen is what measures.
#: These are search coarseness, not a gate: no threshold, floor or law is expressed here.
PARAM_MULTIPLIERS: tuple[float, ...] = (0.5, 1.0, 2.0)

#: How many of a family's own parameters become decision layers. Two, because the episode length
#: is what the agent must credit across, and a 12-layer episode over a 34-family root spends the
#: whole budget before any prefix is visited twice.
PARAM_DEPTH = 2

#: Exploration never stops. See the module docstring: the reward is read off the current book, so
#: a converged agent proposes the book back to itself.
EPSILON_FLOOR = 0.10
EPSILON_START = 1.0
EPSILON_DECAY = 0.999

#: Transitions retained for replay. Bounded on purpose: an unbounded buffer makes the run's
#: memory a function of its episode count, and the desk runs this inside an hourly cycle.
REPLAY_CAPACITY = 20_000

#: Reward bases, reported verbatim on the artifact.
MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"

#: An incomplete specification pays nothing. This is a DEFINITION of the MDP -- the desk cannot
#: trade half a spec, so there is nothing to measure -- and not a measurement of zero.
NO_REWARD = 0.0

Value = str | int | float
Action = tuple[str, Value]
State = tuple[Action, ...]


# ==============================================================================================
# The pieces: transitions, the buffer, the exploration schedule
# ==============================================================================================

class Transition(NamedTuple):
    """One (s, a, r, s') step. `terminal` says the spec was COMPLETE, not that the run ended."""

    state: State
    action: Action
    reward: float
    next_state: State
    terminal: bool


@dataclass
class ReplayBuffer:
    """A bounded ring of transitions, so old credit keeps propagating after its episode ended.

    CAPACITY IS STATED AND ENFORCED (`REPLAY_CAPACITY`, 20,000 transitions). An unbounded buffer
    would make a long run's memory a function of its episode count on a box that also runs the
    live gateway; a ring drops the OLDEST transition, which is the one whose prefix the agent has
    had the most chances to learn from.

    Sampling is done by an explicitly passed generator, never by module-level randomness, so the
    buffer cannot become a hidden source of run-to-run difference.
    """

    capacity: int = REPLAY_CAPACITY
    _rows: list[Transition] = field(default_factory=list)
    _next: int = 0

    def __post_init__(self) -> None:
        if int(self.capacity) <= 0:
            raise ValueError("replay capacity must be positive; an unbounded buffer is refused")
        self.capacity = int(self.capacity)

    def add(self, tr: Transition) -> None:
        if len(self._rows) < self.capacity:
            self._rows.append(tr)
            return
        self._rows[self._next] = tr
        self._next = (self._next + 1) % self.capacity

    def __len__(self) -> int:
        return len(self._rows)

    def rows(self) -> tuple[Transition, ...]:
        return tuple(self._rows)

    def sample(self, n: int, rng: np.random.Generator) -> list[Transition]:
        if not self._rows or n <= 0:
            return []
        idx = rng.integers(0, len(self._rows), size=int(min(n, len(self._rows))))
        return [self._rows[int(i)] for i in idx]


@dataclass(frozen=True)
class EpsilonGreedy:
    """Exploration rate with a FLOOR THAT IS NEVER ZERO.

    `value(step) = max(floor, start * decay**step)`. The floor is checked at construction and a
    non-positive one is refused: see the module docstring for why an agent that stops exploring
    is an agent that proposes the desk's existing book back to itself.
    """

    start: float = EPSILON_START
    decay: float = EPSILON_DECAY
    floor: float = EPSILON_FLOOR

    def __post_init__(self) -> None:
        if not (self.floor > 0.0):
            raise ValueError(
                "epsilon floor must be > 0: an agent that stops exploring converges on the "
                "current book, which is the one region where new alpha is worth least")
        if not (0.0 < self.decay <= 1.0):
            raise ValueError("epsilon decay must be in (0, 1]")

    def value(self, step: int) -> float:
        return float(max(self.floor, self.start * (self.decay ** max(0, int(step)))))


# ==============================================================================================
# The learner
# ==============================================================================================

class MDP(Protocol):
    """What `run_episodes` needs. Implemented by `AlphaMDP`; a toy implements it in the tests."""

    def actions(self, state: State) -> tuple[Action, ...]: ...

    def is_terminal(self, state: State) -> bool: ...


#: A reward function answers a COMPLETED state with `(value, why)`. `None` means the coordinate
#: is unpriced by the book and the episode must be discarded -- never scored as zero.
RewardFn = Callable[[State], tuple[float | None, str]]


@dataclass
class QLearner:
    """Tabular Q over (partial spec, next decision), updated by one-step Q-learning.

        Q(s,a) <- Q(s,a) + lr * (r + gamma * max_a' Q(s',a') - Q(s,a))

    TABULAR, NOT LINEAR-APPROXIMATED, and that is the honest choice for this state space. The
    state is a PREFIX, so states are shared by construction: every completion under `carry`
    updates the same root entry. A function approximator would buy generalisation ACROSS prefixes
    -- "metals behave like metals" -- which is a claim about the universe that nothing here has
    measured, and it would be indistinguishable in the report from evidence.

    `gamma` is 1.0 by default. Discounting exists to trade a reward now against a reward later;
    here every episode is the same fixed number of decisions and the only reward arrives at the
    end, so any gamma < 1 would silently rank SHORT prefixes above long ones for a reason that
    has nothing to do with the book.
    """

    lr: float = 0.5
    gamma: float = 1.0
    seed: int = 0
    q: dict[tuple[State, Action], float] = field(default_factory=dict)
    visits: dict[tuple[State, Action], int] = field(default_factory=dict)
    updates: int = 0

    def __post_init__(self) -> None:
        if not (0.0 < self.lr <= 1.0):
            raise ValueError("learning rate must be in (0, 1]")
        if not (0.0 < self.gamma <= 1.0):
            raise ValueError("gamma must be in (0, 1]")

    # ---------------------------------------------------------------- reading the table
    def value(self, state: State, action: Action) -> float:
        return float(self.q.get((state, action), 0.0))

    def best(self, state: State, actions: Sequence[Action]) -> float:
        """max_a Q(s,a). Zero for a state with no actions -- a terminal bootstraps to nothing."""
        return max((self.value(state, a) for a in actions), default=0.0)

    def greedy(self, state: State, actions: Sequence[Action]) -> Action | None:
        """The best action, ties broken by the action's own sort order -- never by chance.

        A random tie-break would make two runs on one seed differ in the ORDER their equal-valued
        prefixes were visited, and the report ranks prefixes.
        """
        if not actions:
            return None
        return max(sorted(actions), key=lambda a: self.value(state, a))

    # ---------------------------------------------------------------- the update
    def update(self, tr: Transition, next_actions: Sequence[Action]) -> None:
        key = (tr.state, tr.action)
        boot = 0.0 if tr.terminal else self.gamma * self.best(tr.next_state, next_actions)
        cur = self.q.get(key, 0.0)
        self.q[key] = cur + self.lr * (float(tr.reward) + boot - cur)
        self.visits[key] = self.visits.get(key, 0) + 1
        self.updates += 1

    def learn(self, trajectory: Sequence[Transition], mdp: MDP) -> None:
        """Apply one trajectory BACKWARDS, terminal step first.

        WHY BACKWARDS AND WHY IT IS THE TEST THAT DISTINGUISHES THIS FROM A BANDIT. Forwards, a
        terminal reward reaches the root only after as many episodes as the episode is long,
        because each sweep moves credit exactly one layer. Backwards, the terminal step is
        updated before the step that led to it, so the whole trajectory's credit reaches the
        FIRST decision within a single episode. `Q(root, family)` therefore becomes non-zero from
        what happened four decisions later -- which is precisely the quantity a bandit over
        finished candidates cannot represent.
        """
        for tr in reversed(list(trajectory)):
            self.update(tr, () if tr.terminal else mdp.actions(tr.next_state))

    def replay(self, buffer: ReplayBuffer, n: int, mdp: MDP, rng: np.random.Generator) -> int:
        drawn = buffer.sample(n, rng)
        for tr in drawn:
            self.update(tr, () if tr.terminal else mdp.actions(tr.next_state))
        return len(drawn)

    # ---------------------------------------------------------------- reading it out
    def top_prefixes(self, n: int = 25) -> list[dict[str, Any]]:
        """The highest-valued (partial spec, next decision) pairs, with their visit counts.

        The visit count rides beside the Q ON PURPOSE: a Q of 4.1 seen once is a single episode's
        reward, not a value, and a reader who cannot see the denominator cannot tell them apart.
        """
        rows: list[dict[str, Any]] = [
            {"prefix": [list(d) for d in state],
             "decision": list(action),
             "depth": len(state),
             "q": round(float(v), 8),
             "visits": int(self.visits.get((state, action), 0))}
            for (state, action), v in self.q.items()
        ]
        rows.sort(key=lambda r: (-float(r["q"]), int(r["depth"]),
                                 str(r["prefix"]), str(r["decision"])))
        return rows[: max(0, int(n))]

    def table(self) -> dict[str, float]:
        """The Q table with string keys, in sorted order -- the artifact's determinism check."""
        return {f"{list(s)}|{list(a)}": round(float(v), 10)
                for (s, a), v in sorted(self.q.items(), key=lambda kv: str(kv[0]))}


# ==============================================================================================
# The desk's own MDP
# ==============================================================================================

def orthogonal_families() -> tuple[tuple[str, ...], str]:
    """Family names from `mt5desk.families_orthogonal.ORTHOGONAL_FAMILIES`, or () and the reason.

    IMPORTED, NEVER RE-LISTED. A copy of this list here would let the agent search families the
    desk cannot execute, and would go stale silently the next time a family is registered -- the
    exact failure mode the registry exists to prevent.
    """
    try:
        from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    except Exception as exc:                                             # pragma: no cover
        return (), f"ORTHOGONAL_FAMILIES unimportable ({type(exc).__name__}: {exc})"
    return tuple(sorted(ORTHOGONAL_FAMILIES)), f"{len(ORTHOGONAL_FAMILIES)} registered families"


def desk_universe(path: Path | None = None) -> tuple[tuple[str, ...], str]:
    """Tradable symbols from the desk's OWN Fusion symbol table. Never a hand-written list.

    THIS IS WHAT MAKES THE MT5 MANDATE STRUCTURAL. The file is written by
    `mt5desk.universe_registry.merge` from the broker's own `symbol_info`, so every action at the
    symbol layer is a Fusion-executable instrument by construction -- FX, metals, indices,
    energy, softs, share CFDs, and the crypto CFDs Fusion itself offers. A crypto-EXCHANGE-native
    name has no route into this tuple, so it cannot be an action, cannot be scored and cannot be
    emitted. There is no filter to forget, because there is no other source.

    A symbol with no recorded bars is excluded and counted: an action that cannot be screened is
    an action that wastes the agent's whole exploration budget on a coordinate that can never
    return a reward.
    """
    p = path or UNIVERSE_JSON
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return (), f"no symbol registry at {p} ({type(exc).__name__}): symbol layer empty"
    if not isinstance(doc, dict):
        return (), f"{p} is not a mapping: symbol layer empty"
    syms, no_bars = [], 0
    for name, row in doc.items():
        if name.startswith("_") or not isinstance(row, dict):
            continue
        try:
            bars = int(row.get("bars") or 0)
        except (TypeError, ValueError):
            bars = 0
        if bars <= 0:
            no_bars += 1
            continue
        syms.append(str(name))
    why = f"{len(syms)} Fusion symbols with recorded bars from {p.name}"
    if no_bars:
        why += f"; {no_bars} excluded for having no bars on disk"
    return tuple(sorted(syms)), why


def session_windows() -> tuple[dict[str, tuple[int, int]], str]:
    """Named broker-hour windows from `libs.research_os.dsl.SESSIONS` (Fusion runs UTC+3)."""
    try:
        from libs.research_os.dsl import SESSIONS
    except Exception as exc:                                             # pragma: no cover
        return {}, f"SESSIONS unimportable ({type(exc).__name__}: {exc})"
    return dict(SESSIONS), f"{len(SESSIONS)} named windows on the broker's UTC+3 clock"


def _timeframes(family: str) -> tuple[str, ...]:
    """The charts THIS family may be enumerated on, from the registry's own declaration.

    `timeframe_domain` is the desk's answer to "may this mechanism be asked on a D1 bar?" -- e.g.
    `execution_state` reads a surface published by stamp hour and is refused above H1. Reading it
    here means the agent cannot spend an episode on a cell the sweep would refuse to build.
    """
    try:
        from mt5desk.families_orthogonal import timeframe_domain
        return tuple(timeframe_domain(family))
    except Exception:                                                    # pragma: no cover
        try:
            from mt5desk.universe_registry import TIMEFRAMES
            return tuple(TIMEFRAMES)
        except Exception:
            return ()


def family_hour_param(family: str) -> str | None:
    """The family's own hour-valued parameter, if it has one -- how a session becomes a spec.

    A family whose signature names no hour (`carry`, `vol_transition`, ...) has no way to express
    "London". Handing it a session anyway would produce two specs that compile to one identical
    cell: the desk's identity law would then see a collision this module manufactured. Such a
    family gets exactly one session action, `SESSION_ANY`.
    """
    fn = _family_fn(family)
    if fn is None:
        return None
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):                                      # pragma: no cover
        return None
    for name, p in params.items():
        if "hour" in name and isinstance(p.default, (int, float)) \
                and not isinstance(p.default, bool):
            return name
    return None


def _family_fn(family: str) -> Any:
    try:
        from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
        return ORTHOGONAL_FAMILIES.get(family)
    except Exception:                                                    # pragma: no cover
        return None


def family_param_axes(family: str, depth: int = PARAM_DEPTH) -> list[tuple[str, tuple[Value, ...]]]:
    """Decision layers read off the family's OWN signature: `(param, grid)` in signature order.

    THE GRID IS ANCHORED ON THE FAMILY'S OWN DEFAULT and nowhere else. `PARAM_MULTIPLIERS` scales
    it; an int default stays an int (a bar count of 7.5 is not a bar count), a float stays a
    float, and a multiplier that collapses onto its neighbour is dropped rather than offered as a
    distinct decision the agent would waste episodes distinguishing. A family that changes a
    default moves this grid with it -- there is no second copy of the number here to go stale.

    Hour parameters are excluded: the session layer already owns them, and offering the same
    parameter on two layers lets the later one silently overwrite the earlier one's decision.
    """
    fn = _family_fn(family)
    if fn is None:
        return []
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):                                      # pragma: no cover
        return []
    hour = family_hour_param(family)
    out: list[tuple[str, tuple[Value, ...]]] = []
    for name, p in params.items():
        if len(out) >= max(0, int(depth)):
            break
        if name == hour or "hour" in name or p.kind is inspect.Parameter.VAR_KEYWORD:
            continue
        d = p.default
        if isinstance(d, bool) or not isinstance(d, (int, float)) or not math.isfinite(float(d)):
            continue
        if float(d) == 0.0:
            continue
        grid: list[Value] = []
        for m in PARAM_MULTIPLIERS:
            v: Value = round(float(d) * m) if isinstance(d, int) else round(float(d) * m, 6)
            if isinstance(v, int) and v <= 0:
                continue
            if v not in grid:
                grid.append(v)
        if len(grid) > 1:
            out.append((name, tuple(grid)))
    return out


@dataclass
class AlphaMDP:
    """The alpha-construction MDP over the desk's registries. Every action set is imported.

    State is a TUPLE OF DECISIONS TAKEN so far, in a fixed layer order, so a state IS a prefix
    and two specs that agree on their first k decisions share the same k states. That sharing is
    the whole mechanism: it is what lets a reward earned by one completion move the value of a
    decision three layers above it.
    """

    families: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    sessions: tuple[str, ...] = ()
    param_depth: int = PARAM_DEPTH
    inputs: dict[str, str] = field(default_factory=dict)

    #: Fixed layer order. The state's length is its layer, which is what makes it a prefix.
    LAYERS: tuple[str, ...] = ("family", "symbol", "session", "timeframe")

    @classmethod
    def from_registries(cls, *, symbols: Sequence[str] | None = None,
                        universe_path: Path | None = None,
                        param_depth: int = PARAM_DEPTH) -> AlphaMDP:
        fams, fam_why = orthogonal_families()
        uni, uni_why = desk_universe(universe_path)
        sess, sess_why = session_windows()
        chosen = tuple(sorted({str(s) for s in symbols} & set(uni))) if symbols else uni
        inputs = {
            "families": fam_why,
            "symbols": uni_why + (f"; restricted to {len(chosen)} requested" if symbols else ""),
            "sessions": sess_why,
            "timeframes": "per family, from families_orthogonal.timeframe_domain",
            "parameters": (f"first {param_depth} numeric non-hour parameters of each family's own "
                           f"signature, at {PARAM_MULTIPLIERS} of its own default"),
        }
        return cls(families=fams, symbols=chosen, sessions=tuple(sorted(sess)),
                   param_depth=int(param_depth), inputs=inputs)

    # ---------------------------------------------------------------- the transition function
    def _family_of(self, state: State) -> str:
        for k, v in state:
            if k == "family":
                return str(v)
        return ""

    def _param_axes(self, state: State) -> list[tuple[str, tuple[Value, ...]]]:
        fam = self._family_of(state)
        return family_param_axes(fam, self.param_depth) if fam else []

    def layer(self, state: State) -> str | None:
        """The name of the decision due next, or None when the spec is complete."""
        n = len(state)
        if n < len(self.LAYERS):
            return self.LAYERS[n]
        axes = self._param_axes(state)
        i = n - len(self.LAYERS)
        return axes[i][0] if i < len(axes) else None

    def actions(self, state: State) -> tuple[Action, ...]:
        """Every decision available at `state`, always in sorted order (determinism)."""
        key = self.layer(state)
        if key is None:
            return ()
        if key == "family":
            return tuple(("family", f) for f in self.families)
        if key == "symbol":
            return tuple(("symbol", s) for s in self.symbols)
        if key == "session":
            fam = self._family_of(state)
            if family_hour_param(fam) is None:
                return (("session", SESSION_ANY),)
            return tuple(("session", s) for s in self.sessions)
        if key == "timeframe":
            return tuple(("timeframe", t) for t in _timeframes(self._family_of(state)))
        for name, grid in self._param_axes(state):
            if name == key:
                return tuple((name, v) for v in grid)
        return ()                                                        # pragma: no cover

    def is_terminal(self, state: State) -> bool:
        return self.layer(state) is None and len(state) >= len(self.LAYERS)

    # ---------------------------------------------------------------- reading a state out
    def spec(self, state: State) -> dict[str, Any]:
        """A completed state as `{symbol, family, session, timeframe, params}`.

        The session is folded into the family's OWN hour parameter, so what the compiler receives
        is a parameter the family actually accepts -- never a key it would drop on the floor.
        """
        d = dict(state)
        fam = str(d.get("family", ""))
        params = {k: v for k, v in state if k not in self.LAYERS}
        hour = family_hour_param(fam)
        sess = str(d.get("session", SESSION_ANY))
        windows, _ = session_windows()
        if hour and sess in windows:
            params[hour] = int(windows[sess][0])
        return {"symbol": str(d.get("symbol", "")), "family": fam, "session": sess,
                "timeframe": str(d.get("timeframe", "")), "params": dict(sorted(params.items()))}


# ==============================================================================================
# Reward: the book's own marginal dE[log W], or a refusal
# ==============================================================================================

def _sleeve_axes(name: str) -> dict[str, str]:
    """Split an allocator sleeve name into axes, using the desk's own parser when reachable.

    `desks/mt5/research/portfolio_gap.sleeve_axes` is the desk's parser and is preferred, so this
    module cannot drift from how `session_capital` and `hour_surface` read the same keys. The
    fallback mirrors it exactly and exists only so `libs/` stays importable without the desk on
    the path; it is not a second opinion about the format.
    """
    try:
        from portfolio_gap import sleeve_axes  # type: ignore[import-not-found]

        return dict(sleeve_axes(name))
    except Exception:
        pass
    if name.startswith("gold_"):
        return {"symbol": "XAUUSD", "window": name[len("gold_"):], "state": "",
                "family": "session_bracket", "side": ""}
    m = re.match(r"^([A-Za-z0-9]+)_(.+?)_([A-Z]+_DAY)$", name)
    if m:
        return {"symbol": m.group(1), "window": m.group(2), "state": m.group(3),
                "family": "session_bracket", "side": ""}
    parts = name.split("_")
    return {"symbol": parts[0], "window": parts[-1] if len(parts) > 1 else "",
            "state": "", "family": "_".join(parts[1:-1]) or "unspecified", "side": ""}


def _finite(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


@dataclass
class BookReward:
    """Marginal dE[log W] read off the allocator's artifact. Refuses rather than invents.

    `basis` is `MEASURED` only when the artifact exists AND carries at least one finite marginal.
    Otherwise it is `UNMEASURED`, `why` says which of the two failed, and `run_episodes` applies
    NO updates at all -- see the module docstring for why a fabricated reward is worse than none.

    A completed spec is priced at the FINEST coordinate the book has actually valued:

        exact          the book holds this (symbol, family, window) -- its own measured marginal
        symbol_family  the book holds this instrument in this family at other windows -- their
                       mean, which is a measured number about a real coordinate
        family         the book holds this mechanism elsewhere -- the family's measured mean
        (none)         UNPRICED: the book has never valued this coordinate. The episode is
                       DISCARDED. It is not scored zero, because zero would assert that admitting
                       it adds nothing, and nobody measured that.

    The match depth rides on every reward and is counted in the report, so a reader can see how
    much of a run's learning came from an exact match and how much from a family-level mean.
    """

    basis: str = UNMEASURED
    why: str = "not loaded"
    detail: str = ""
    by_exact: dict[tuple[str, str, str], float] = field(default_factory=dict)
    by_symbol_family: dict[tuple[str, str], list[float]] = field(default_factory=dict)
    by_family: dict[str, list[float]] = field(default_factory=dict)
    funded: set[tuple[str, str, str]] = field(default_factory=set)
    n_priced: int = 0

    @classmethod
    def from_artifact(cls, path: Path | None = None) -> BookReward:
        p = path or PF_ALLOCATION
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError) as exc:
            return cls(basis=UNMEASURED,
                       why=(f"no allocator artifact at {p} ({type(exc).__name__}): there is no "
                            "book to measure a marginal against, so every episode is UNMEASURED "
                            "and contributes no update"))
        if not isinstance(doc, dict):
            return cls(basis=UNMEASURED, why=f"{p} is not a mapping: no book to measure against")
        marginal, detail = cls._marginals(doc)
        if not marginal:
            return cls(basis=UNMEASURED,
                       why=(f"{p.name} carries no finite marginal dE[logW] "
                            f"({detail}): nothing measured, so nothing is learned"))
        self = cls(basis=MEASURED,
                   why=f"{len(marginal)} measured marginals from {p.name}", detail=detail,
                   n_priced=len(marginal))
        for name, val in sorted(marginal.items()):
            ax = _sleeve_axes(name)
            sym, fam, win = ax.get("symbol", ""), ax.get("family", ""), ax.get("window", "")
            self.by_exact[(sym, fam, win)] = val
            self.by_symbol_family.setdefault((sym, fam), []).append(val)
            self.by_family.setdefault(fam, []).append(val)
            self.funded.add((sym, fam, win))
        return self

    @staticmethod
    def _marginals(doc: dict[str, Any]) -> tuple[dict[str, float], str]:
        """The admission marginal where the artifact carries it, else the solved-book gradient.

        The desk keeps these apart on purpose (pf_allocator.py's own comment): the gradient is
        the value of a FUNDED sleeve's last unit of heat, while `delta_elogw_per_day` re-solves
        the whole book around a candidate it does NOT hold. The reward is defined as the latter,
        so the latter is preferred and the report names which one was used.
        """
        adm = doc.get("admission")
        if isinstance(adm, dict) and isinstance(adm.get("candidates"), dict):
            rows = {str(k): _finite((v or {}).get("delta_elogw_per_day"))
                    for k, v in adm["candidates"].items() if isinstance(v, dict)}
            got = {k: v for k, v in rows.items() if v is not None}
            if got:
                return got, ("admission.candidates[*].delta_elogw_per_day -- the marginal of "
                             "ADMITTING a sleeve the book does not hold, which is what the "
                             "reward is defined as")
        grad = doc.get("marginal_delta_elog")
        if isinstance(grad, dict):
            rows2 = {str(k): _finite(v) for k, v in grad.items()}
            got2 = {k: v for k, v in rows2.items() if v is not None}
            if got2:
                return got2, ("marginal_delta_elog -- the GRADIENT of the robust objective at "
                              "the solved book (the value of each funded sleeve's last unit of "
                              "heat). Used because the artifact carried no admission block; it "
                              "is a property of sleeves the book HOLDS, not of a new one")
        return {}, "neither an admission block nor a finite marginal_delta_elog map"

    # ---------------------------------------------------------------- the reward itself
    def price(self, spec: dict[str, Any]) -> tuple[float | None, str]:
        sym = str(spec.get("symbol", ""))
        fam = str(spec.get("family", ""))
        win = str(spec.get("session", ""))
        if self.basis != MEASURED:
            return None, self.why
        hit = self.by_exact.get((sym, fam, win))
        if hit is not None:
            return float(hit), "exact"
        rows = self.by_symbol_family.get((sym, fam))
        if rows:
            return float(sum(rows) / len(rows)), "symbol_family"
        rows = self.by_family.get(fam)
        if rows:
            return float(sum(rows) / len(rows)), "family"
        return None, "unpriced: the book has never valued this coordinate"

    def is_funded(self, spec: dict[str, Any]) -> bool:
        """Whether the book already holds this exact coordinate -- not a research candidate."""
        return (str(spec.get("symbol", "")), str(spec.get("family", "")),
                str(spec.get("session", ""))) in self.funded

    def __call__(self, state: State, spec: dict[str, Any]) -> tuple[float | None, str]:
        return self.price(spec)


# ==============================================================================================
# Running episodes
# ==============================================================================================

class Episode(NamedTuple):
    state: State
    spec: dict[str, Any]
    reward: float | None
    basis: str


@dataclass
class RunResult:
    episodes: int = 0
    rewarded: int = 0
    unpriced: int = 0
    truncated: int = 0
    updates: int = 0
    replayed: int = 0
    reward_basis: str = UNMEASURED
    reward_why: str = ""
    reward_detail: str = ""
    match_depths: dict[str, int] = field(default_factory=dict)
    completed: list[Episode] = field(default_factory=list)
    states_visited: int = 0
    epsilon_final: float = EPSILON_FLOOR


def run_episodes(mdp: MDP, learner: QLearner, reward: RewardFn, *, episodes: int,
                 rng: np.random.Generator, buffer: ReplayBuffer | None = None,
                 epsilon: EpsilonGreedy | None = None, replay_per_episode: int = 8,
                 budget_s: float | None = None, clock: Callable[[], float] | None = None,
                 basis: str = MEASURED, basis_why: str = "") -> RunResult:
    """Roll out `episodes` trajectories, learning only from rewards that were MEASURED.

    THE REFUSAL IS AT THE TOP OF THE LOOP AND IT IS TOTAL. With `basis != MEASURED` -- no
    allocator artifact, or one with no finite marginal -- the episodes are not run at all: no
    transition is created, no transition enters the buffer, and the Q table is returned EMPTY.
    Rolling out and updating with a placeholder reward would produce a confident ranking of a
    fabrication, and a reader of the artifact could not tell it from a ranking earned against a
    real book.

    An episode whose completed spec is UNPRICED is discarded WHOLE -- its transitions never reach
    the buffer -- for the same reason one layer down: the agent may only learn from coordinates
    the allocator has actually valued.
    """
    eps = epsilon or EpsilonGreedy()
    buf = buffer if buffer is not None else ReplayBuffer()
    now = clock or (lambda: 0.0)
    res = RunResult(reward_basis=basis, reward_why=basis_why, epsilon_final=eps.value(0))
    if basis != MEASURED:
        res.reward_why = basis_why or "reward basis is not MEASURED"
        return res
    started = now()
    seen: set[State] = set()
    for ep in range(max(0, int(episodes))):
        if budget_s is not None and (now() - started) > float(budget_s):
            break
        e = eps.value(ep)
        res.epsilon_final = e
        state: State = ()
        traj: list[Transition] = []
        while not mdp.is_terminal(state):
            acts = mdp.actions(state)
            if not acts:
                break
            if rng.random() < e:
                choice = acts[int(rng.integers(0, len(acts)))]
            else:
                picked = learner.greedy(state, acts)
                choice = picked if picked is not None else acts[0]
            nxt: State = (*state, choice)
            traj.append(Transition(state, choice, NO_REWARD, nxt, False))
            seen.add(state)
            state = nxt
        res.episodes += 1
        seen.add(state)
        if not traj or not mdp.is_terminal(state):
            res.truncated += 1
            continue
        spec = mdp.spec(state) if hasattr(mdp, "spec") else dict(state)
        _rw: Any = reward
        r, depth = _rw(state, spec) if _takes_two(reward) else _rw(state)
        if r is None:
            res.unpriced += 1
            continue
        traj[-1] = traj[-1]._replace(reward=float(r), terminal=True)
        for tr in traj:
            buf.add(tr)
        learner.learn(traj, mdp)
        res.rewarded += 1
        res.match_depths[depth] = res.match_depths.get(depth, 0) + 1
        res.completed.append(Episode(state, spec, float(r), depth))
        res.replayed += learner.replay(buf, replay_per_episode, mdp, rng)
    res.updates = learner.updates
    res.states_visited = len(seen)
    return res


def _takes_two(fn: Any) -> bool:
    """Whether the reward function wants `(state, spec)` or only `(state)`.

    Both shapes exist for a reason: `BookReward` needs the compiled spec (the session must be
    folded into the family's own hour parameter before the book can be asked about it), while a
    toy MDP in a test has no spec to compile and answers from the state alone.
    """
    try:
        return len(inspect.signature(fn).parameters) >= 2
    except (TypeError, ValueError):                                      # pragma: no cover
        return False


def deterministic_replay(transitions: Iterable[Transition], mdp: MDP, *, lr: float = 0.5,
                         gamma: float = 1.0) -> QLearner:
    """Rebuild a Q table from a fixed transition set. Two calls must agree byte for byte.

    The determinism guarantee this module makes is about the LEARNER, not about the market: given
    the same transitions and the same hyper-parameters, the table is a pure function of them.
    """
    q = QLearner(lr=lr, gamma=gamma)
    rows = list(transitions)
    for tr in rows:
        q.update(tr, () if tr.terminal else mdp.actions(tr.next_state))
    return q
