"""MCTS over the research tree: a beam never comes back, a tree learns where to spend.

WHAT F6 HAS AND WHAT IT DOES NOT (ledger D7 and Q15, measured 2026-09-16).
`desks/mt5/research/research_tree.py` scores every frontier node by the exact expected entropy
reduction of its Beta posterior per cell-equivalent and expands the top BEAM of that ranking.
That is best-first search, and best-first search has the property this desk keeps paying for:
IT NEVER COMES BACK. A node is scored once, from evidence its parent held before the expansion,
and no result ever revises the ranking that spent the hour. Twelve nodes are expanded, the
thirteenth waits, and nothing the twelve found changes which one is thirteenth.

A TREE THAT LEARNS WHERE TO SPEND does four things a beam cannot, and all four are here:

    SELECTION       descend from the root by PUCT -- the child's MEASURED mean reward plus an
                    exploration term that is large while the child is untried and shrinks as it
                    is tried. The desk's own `_score` supplies the prior, so a variant of a
                    productive mechanism starts ahead of a fresh idea and stops being ahead the
                    moment its own rollouts disagree.
    EXPANSION       spawn the next kind down -- the caller's `_children_for`, unchanged. This
                    library never invents a research question. It decides WHERE the next one is
                    asked, and the KINDS ladder still decides what may be asked there.
    ROLLOUT         one cheap in-sample screen, supplied by the caller. A screen that cannot
                    measure the node returns None, and None updates NOTHING: it is not a zero
                    reward, it moves no posterior and it sinks no branch (L1.28a). It is
                    COUNTED, because a branch nothing can screen is a fact worth reading.
    BACKPROPAGATION the reward walks back up the path it came down, so a good leaf raises the
                    value of every ancestor that led to it. That is the step a beam has no way
                    to express, and it is the one that makes attention self-correcting.

FREQUENT-SUBTREE AVOIDANCE (Alpha Jungle). PUCT alone concentrates: `1 + n` in the denominator
slows a monopolist and never stops one, and `discovered` is 17,151 of 21,572 docket cells
because nothing ever stopped one. The penalty here is explicit and additive -- a child pays in
proportion to how far its share of its siblings' attempts exceeds an even share -- so a branch
holding four fifths of the attention must be four fifths better to keep it.
`lineage_dag.subtree_penalty` penalises the CONCEPTUAL rut across the whole graveyard; this
penalises the ATTENTION rut inside one live tree. `concept_rut_penalty` composes the two, which
is the wiring the ledger records as missing.

UNMEASURED IS A REAL ANSWER, AND IT STILL MAY NOT MONOPOLISE. A rollout returning None never
touches `visits`, `value` or any posterior. But if the exploration term were driven by `visits`
alone, an unscreenable branch would be re-selected forever at full optimism -- absence would buy
the whole budget. So the exploration denominator and the penalty share both count ATTEMPTS
(visits + unmeasured) while Q counts only what was measured. Absence stops costing the tree
without ever being scored as a failure.

PROJECTS, NOT NODES (AI-Scientist-v2, Q15). `project_tree` builds a whole research project as a
tree -- macro liquidity -> asset classes -> mechanisms -> instruments -- whose leaves are cell
specs, and `experiment_manager` splits one budget of rollouts across several such projects by
what each project's frontier is measurably worth. Every project keeps a FLOOR of that budget: a
project with nothing measured yet has no value, and no value is not evidence of no value.

NOTHING HERE CERTIFIES ANYTHING. The tree allocates attention; the cells it names reach the book
through the identical ten gates. Visit counts and values are written into the CALLER's own node
dicts, and the caller saves them.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeAlias

import numpy as np

#: One node of the caller's tree. A plain mapping, because that is what
#: `desks/mt5/data/research_tree.json` already holds, and a search that demanded its own node
#: class would force the desk to re-shape a persistent artifact in order to be searched.
#: REQUIRED: `id`. READ IF PRESENT: `parent`, `kind`, `label`, `children` (ids), `state` (a node
#: whose state is not OPEN is never descended into -- research_tree's pruning is permanent),
#: `prior` (research_tree `_score`'s posterior_value), `evidence` {alpha, beta} or
#: `successes`/`trials`, `spec`, `concepts`.
#: WRITTEN BY THIS LIBRARY: `visits`, `value`, `value_sum`, `unmeasured`, `clipped`, `children`.
Node: TypeAlias = MutableMapping[str, Any]
Nodes: TypeAlias = MutableMapping[str, Node]
#: The caller's own child factory -- `research_tree._children_for` with its symbols bound.
Spawn: TypeAlias = Callable[[Node], Sequence[Mapping[str, Any]]]
#: A cheap in-sample screen. None means UNMEASURED and updates nothing.
Screen: TypeAlias = Callable[[Node], float | None]
#: (nodes, node_id, siblings) -> an additive penalty subtracted from that node's PUCT score.
Penalty: TypeAlias = Callable[[Nodes, str, Sequence[str]], float]

#: Exploration weight. 1.4 is AlphaZero's neighbourhood and is STATED, not tuned: with rewards on
#: [0, 1] it lets a never-tried child with a mid prior outrank a sibling holding a 0.5 mean.
C_PUCT = 1.4
#: What a total monopolist pays. Half the reward range: strong enough that a branch cannot hold
#: the tree on inertia, weak enough that a branch which is genuinely twice as good keeps it.
PENALTY_WEIGHT = 0.5
#: The floor share of an experiment budget every project keeps, however poorly it has scored.
MIN_SHARE = 0.10
FRONTIER_K = 8


# --------------------------------------------------------------------------- reading a node

def _num(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def _open(node: Mapping[str, Any]) -> bool:
    """A missing state is OPEN. Only an explicit non-OPEN state closes a branch."""
    return str(node.get("state", "OPEN")).upper() == "OPEN"


def node_id(kind: str, parent: str | None, label: str) -> str:
    """The caller's own id shape (`research_tree._node_id`), so ids collide where they should."""
    return f"{parent or 'root'}|{kind}:{label}"


def evidence(node: Mapping[str, Any]) -> tuple[float, float]:
    """The node's Beta evidence, from whichever of the three shapes the caller wrote."""
    ev = node.get("evidence")
    if isinstance(ev, Mapping):
        a, b = _num(ev.get("alpha")), _num(ev.get("beta"))
        if a > 0.0 and b > 0.0:
            return a, b
    a, b = _num(node.get("alpha")), _num(node.get("beta"))
    if a > 0.0 and b > 0.0:
        return a, b
    s = max(0.0, _num(node.get("successes")))
    t = max(s, _num(node.get("trials")))
    return 1.0 + s, 1.0 + (t - s)


def prior(node: Mapping[str, Any]) -> float:
    """P(this node) for PUCT: the tree's `_score` posterior_value if it wrote one, else Beta."""
    p = node.get("prior")
    if p is not None:
        v = _num(p, -1.0)
        if 0.0 <= v <= 1.0:
            return v
    a, b = evidence(node)
    return a / (a + b)


def visits(node: Mapping[str, Any]) -> int:
    """MEASURED simulations through this node -- and, because every simulation starts at the
    root, through its whole subtree. That identity is what the frequent-subtree penalty reads."""
    return max(0, int(_num(node.get("visits"))))


def value(node: Mapping[str, Any]) -> float:
    """Mean MEASURED reward. Only `backpropagate` moves it."""
    return _num(node.get("value"))


def unmeasured(node: Mapping[str, Any]) -> int:
    """Rollouts the screen could not measure. Recorded, never scored as a failure."""
    return max(0, int(_num(node.get("unmeasured"))))


def attempts(node: Mapping[str, Any]) -> int:
    """Visits plus unmeasured rollouts. Exploration and the penalty spend this; Q never does."""
    return visits(node) + unmeasured(node)


def init_node(node: Node) -> Node:
    """Add this library's fields without disturbing one the caller already owns."""
    for key, default in (("visits", 0), ("value", 0.0), ("value_sum", 0.0), ("unmeasured", 0)):
        node.setdefault(key, default)
    return node


def children_index(nodes: Nodes) -> dict[str, list[str]]:
    """Parent pointers first (research_tree stores only those), then any declared `children`."""
    idx: dict[str, list[str]] = {nid: [] for nid in nodes}
    for nid, n in nodes.items():
        p = n.get("parent")
        if isinstance(p, str) and p != nid and p in idx:
            idx[p].append(nid)
    for nid, n in nodes.items():
        declared = n.get("children")
        if isinstance(declared, list | tuple):
            for c in declared:
                if isinstance(c, str) and c != nid and c in nodes and c not in idx[nid]:
                    idx[nid].append(c)
    for kids in idx.values():
        kids.sort()
    return idx


def path_to(nodes: Nodes, leaf_id: str) -> list[str]:
    """Root-first ancestry of a node. Cycle-guarded: a malformed tree truncates, never hangs."""
    out: list[str] = []
    seen: set[str] = set()
    cur = leaf_id
    while cur in nodes and cur not in seen:
        seen.add(cur)
        out.append(cur)
        p = nodes[cur].get("parent")
        cur = p if isinstance(p, str) else ""
    out.reverse()
    return out


# ------------------------------------------------------------------------------- penalties

def subtree_visit_penalty(nodes: Nodes, target: str, siblings: Sequence[str],
                          *, weight: float = PENALTY_WEIGHT) -> float:
    """Alpha Jungle, inside one live tree: what this subtree has taken relative to its siblings.

    Zero at an even share and `weight` at a total monopoly, linear between. An only child pays
    nothing -- it has monopolised nothing, because there was nothing else to take.
    """
    sibs = [s for s in siblings if s in nodes]
    if len(sibs) < 2 or target not in nodes:
        return 0.0
    total = float(sum(attempts(nodes[s]) for s in sibs))
    if total <= 0.0:
        return 0.0
    fair = 1.0 / len(sibs)
    share = attempts(nodes[target]) / total
    return weight * max(0.0, share - fair) / (1.0 - fair)


def concept_rut_penalty(ruts: Mapping[tuple[str, ...], Mapping[str, Any]],
                        *, weight: float = PENALTY_WEIGHT) -> Penalty:
    """Wrap `lineage_dag.subtree_penalty`'s graveyard ruts as a selection penalty.

    lineage_dag returns a MULTIPLICATIVE downweight in (0, 1] per conceptual triple; PUCT wants
    an additive charge, so a triple worth 0.4 there costs `weight * 0.6` here. A node with no
    declared `concepts` pays nothing: an unlabelled node is not evidence of a rut.
    """
    table = {tuple(sorted(str(x) for x in k)): _num(v.get("penalty"), 1.0)
             for k, v in ruts.items()}

    def _pen(nodes: Nodes, target: str, siblings: Sequence[str]) -> float:
        node = nodes.get(target)
        cs = sorted({str(c) for c in (node.get("concepts") or ())}) if node else []
        worst = 1.0
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                for k in range(j + 1, len(cs)):
                    worst = min(worst, table.get((cs[i], cs[j], cs[k]), 1.0))
        return weight * (1.0 - worst)

    return _pen


def combine_penalties(*penalties: Penalty) -> Penalty:
    """Attention ruts and conceptual ruts are different facts; a node in both pays for both."""
    def _pen(nodes: Nodes, target: str, siblings: Sequence[str]) -> float:
        return sum(p(nodes, target, siblings) for p in penalties)
    return _pen


# ----------------------------------------------------------------------------------- search

def puct_scores(nodes: Nodes, parent_id: str, children: Sequence[str], *,
                c_puct: float = C_PUCT, penalty: Penalty | None = None) -> dict[str, float]:
    """value + c_puct * prior * sqrt(N_parent) / (1 + n_child) - penalty(child).

    N and n are ATTEMPTS, not visits, so an unscreenable child stops being re-selected at full
    optimism while its measured value stays untouched. Q is `value`, which only a measured
    reward ever moves.
    """
    pen = subtree_visit_penalty if penalty is None else penalty
    root_term = math.sqrt(float(max(1, attempts(nodes[parent_id]))))
    out: dict[str, float] = {}
    for cid in children:
        child = nodes[cid]
        explore = c_puct * prior(child) * root_term / (1.0 + attempts(child))
        out[cid] = value(child) + explore - pen(nodes, cid, children)
    return out


def select(root_id: str, nodes: Nodes, c_puct: float = C_PUCT, penalty: Penalty | None = None,
           *, index: Mapping[str, Sequence[str]] | None = None) -> list[str]:
    """Descend by PUCT to a leaf and return the whole path, root first.

    Ties break on id, never on dict order: the same tree must select the same path twice or the
    trace is not an audit trail. A non-OPEN child is never descended into -- research_tree's
    pruning is permanent, and a search that re-entered a pruned branch would spend exactly the
    hour the pruning existed to save.
    """
    if root_id not in nodes:
        raise KeyError(f"{root_id!r} is not in the tree; a search needs a root that exists")
    idx = children_index(nodes) if index is None else index
    path = [root_id]
    seen = {root_id}
    while True:
        kids = [c for c in idx.get(path[-1], ())
                if c not in seen and c in nodes and _open(nodes[c])]
        if not kids:
            return path
        scores = puct_scores(nodes, path[-1], kids, c_puct=c_puct, penalty=penalty)
        best = min((-scores[c], c) for c in kids)[1]
        path.append(best)
        seen.add(best)


def expand(node: Node, generator: Spawn, nodes: Nodes) -> list[str]:
    """Spawn the next kind down through the CALLER's generator, and return only the NEW ids.

    An id already in the tree is left exactly as it is -- its visits and value are evidence, and
    a re-expansion that reset them would erase the search's own memory.
    """
    new: list[str] = []
    for spec in generator(node):
        cid = str(spec.get("id") or "")
        if not cid or cid in nodes:
            continue
        child: Node = dict(spec)
        child["id"] = cid
        child.setdefault("parent", node.get("id"))
        nodes[cid] = init_node(child)
        new.append(cid)
    if new:
        declared = node.get("children")
        held = ([c for c in declared if isinstance(c, str)]
                if isinstance(declared, list | tuple) else [])
        node["children"] = sorted(set(held) | set(new))
    return new


def rollout(node: Node, screen: Screen) -> float | None:
    """One cheap screen. None, a non-number and a non-finite number are all UNMEASURED.

    NaN is the one worth naming: it is what a screen returns when it divided by an empty window,
    and folding it into a mean as a zero would retire a branch for having had no data.
    """
    raw = screen(node)
    reward = None if raw is None else _num(raw, float("nan"))
    if reward is None or not math.isfinite(reward):
        node["unmeasured"] = unmeasured(node) + 1
        return None
    if reward < 0.0 or reward > 1.0:
        node["clipped"] = max(0, int(_num(node.get("clipped")))) + 1
        reward = min(1.0, max(0.0, reward))
    return reward


def backpropagate(path: Sequence[str], reward: float, nodes: Nodes) -> int:
    """Credit every node on the path, root included. Returns how many were updated."""
    updated = 0
    for nid in path:
        node = nodes.get(nid)
        if node is None:
            continue
        init_node(node)
        node["visits"] = visits(node) + 1
        node["value_sum"] = _num(node.get("value_sum")) + reward
        node["value"] = float(node["value_sum"]) / float(node["visits"])
        updated += 1
    return updated


def step(nodes: Nodes, root_id: str, generator: Spawn, screen: Screen,
         rng: np.random.Generator, budget_evals: int = 1, *,
         c_puct: float = C_PUCT, penalty: Penalty | None = None) -> dict[str, Any]:
    """One full iteration: select, expand a promising leaf, roll out, backpropagate.

    A leaf is expanded only once it has been ATTEMPTED -- the classic rule, and the one that
    stops a single iteration from growing a whole ladder nothing has evidence for. The root is
    the exception: it is a bookkeeping entry that runs nothing, so spending a screen on it would
    buy the desk a number about a node that is not an experiment.
    """
    path = select(root_id, nodes, c_puct, penalty)
    leaf_id = path[-1]
    leaf = nodes[leaf_id]
    added: list[str] = []
    if _open(leaf) and (attempts(leaf) > 0 or leaf_id == root_id):
        added = expand(leaf, generator, nodes)
    if added:
        jitter = rng.random(len(added))
        ranked = sorted(zip(added, jitter, strict=True),
                        key=lambda t: (-prior(nodes[t[0]]), float(t[1]), t[0]))
        targets = [cid for cid, _ in ranked[:max(1, int(budget_evals))]]
    else:
        targets = [leaf_id]
    rewards: list[float] = []
    blank = 0
    for cid in targets:
        reward = rollout(nodes[cid], screen)
        if reward is None:
            blank += 1
            continue
        backpropagate(path if cid == leaf_id else [*path, cid], reward, nodes)
        rewards.append(reward)
    return {"path": path, "leaf": leaf_id, "expanded": added, "evaluated": targets,
            "rewards": [round(r, 6) for r in rewards], "unmeasured": blank,
            "evals": len(targets)}


@dataclass
class Report:
    """What the search spent and what it found. `to_dict` is what the caller writes out."""

    status: str
    root_id: str
    iterations: int
    evaluations: int = 0
    unmeasured: int = 0
    nodes_added: int = 0
    concentration: float = 0.0
    trace: list[dict[str, Any]] = field(default_factory=list)
    best: list[dict[str, Any]] = field(default_factory=list)
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "root_id": self.root_id, "iterations": self.iterations,
                "evaluations": self.evaluations, "unmeasured": self.unmeasured,
                "nodes_added": self.nodes_added, "concentration": round(self.concentration, 6),
                "frontier": self.best, "trace": self.trace, "why": self.why}


def run(nodes: Nodes, root_id: str, generator: Spawn, screen: Screen, *,
        iterations: int = 32, seed: int = 0, c_puct: float = C_PUCT,
        penalty: Penalty | None = None, budget_evals: int = 1,
        frontier_k: int = FRONTIER_K) -> Report:
    """`iterations` full MCTS steps against one root, deterministic under `seed`."""
    rng = np.random.default_rng(seed)
    before = len(nodes)
    rep = Report(status="OK", root_id=root_id, iterations=max(0, int(iterations)))
    for _ in range(rep.iterations):
        t = step(nodes, root_id, generator, screen, rng, budget_evals,
                 c_puct=c_puct, penalty=penalty)
        rep.trace.append(t)
        rep.evaluations += len(t["rewards"])
        rep.unmeasured += int(t["unmeasured"])
    rep.nodes_added = len(nodes) - before
    rep.best = frontier(nodes, frontier_k, root_id=root_id)
    kids = children_index(nodes).get(root_id, [])
    total = float(sum(visits(nodes[c]) for c in kids))
    rep.concentration = (max(visits(nodes[c]) for c in kids) / total) if total > 0.0 else 0.0
    if rep.evaluations == 0:
        rep.status = "UNMEASURED"
        rep.why = (f"{rep.iterations} iteration(s) reached a node the screen could not measure "
                   f"{rep.unmeasured} time(s). No value moved and nothing was pruned: an "
                   f"unscreenable branch is a gap in the screen, never a verdict on the branch.")
    else:
        rep.why = (f"{rep.evaluations} measured rollout(s) over {rep.iterations} iteration(s); "
                   f"{rep.unmeasured} UNMEASURED and folded into nothing. The most-visited child "
                   f"of the root holds {rep.concentration:.1%} of its measured visits.")
    return rep


def frontier(nodes: Nodes, k: int = FRONTIER_K, *,
             root_id: str | None = None) -> list[dict[str, Any]]:
    """The best `k` OPEN leaves by measured value, each with the path that reached it.

    A leaf nothing has measured sorts BELOW every measured one and says so in `measured`. It is
    not ranked as a zero -- a zero is a result, and this leaf has none.
    """
    idx = children_index(nodes)
    rows: list[dict[str, Any]] = []
    for nid, node in nodes.items():
        if not _open(node) or any(_open(nodes[c]) for c in idx.get(nid, ()) if c in nodes):
            continue
        trail = path_to(nodes, nid)
        if root_id is not None and (not trail or trail[0] != root_id):
            continue
        rows.append({"id": nid, "kind": str(node.get("kind") or ""),
                     "label": str(node.get("label") or ""), "value": round(value(node), 6),
                     "visits": visits(node), "unmeasured": unmeasured(node),
                     "measured": visits(node) > 0, "prior": round(prior(node), 6),
                     "spec": node.get("spec"), "path": trail})
    rows.sort(key=lambda r: (not bool(r["measured"]), -float(r["value"]), -int(r["visits"]),
                             str(r["id"])))
    return rows[:max(0, int(k))]


# ---------------------------------------------------------------- projects, and their manager

def _labels_for(level: Sequence[str] | Mapping[str, Sequence[str]], parent: str) -> list[str]:
    if isinstance(level, Mapping):
        vals = level.get(parent)
        return [str(x) for x in vals] if isinstance(vals, list | tuple) else []
    return [str(x) for x in level]


def project_tree(roots: Sequence[Mapping[str, Any]], depth_kinds: Sequence[str]) -> Nodes:
    """Build whole PROJECTS as trees whose leaves are cell specs (AI-Scientist-v2, Q15).

    Each root declares `label`, optional `question`, optional `prior`, optional `spec` (merged
    into every leaf) and `levels` -- one entry per depth, either a flat list applied under every
    parent or a mapping from a parent's label to its own children, which is what makes "metals
    -> XAU/XAG, fx -> EURUSD" expressible. `depth_kinds[0]` names the root's kind and
    `depth_kinds[i]` the kind at depth i; the last kind repeats if the levels run deeper.

    THE DEEPEST LEVEL IS THE INSTRUMENT LEVEL, and that is a contract rather than a convention:
    the leaf's spec carries `symbol`, which is what `research_tree._donate` pops to build a cell.
    Give the deepest level a kind `_donate` recognises, or the project's leaves rank, deepen and
    never reach the gauntlet.
    """
    if not depth_kinds:
        raise ValueError("depth_kinds is empty; a project tree needs at least a kind for its root")
    nodes: Nodes = {}
    for project in roots:
        label = str(project.get("label") or "").strip()
        if not label:
            raise ValueError("every project root needs a label; an unnamed project cannot be "
                             "allocated to, reported on, or argued with")
        kind = depth_kinds[0]
        rid = node_id(kind, None, label)
        nodes[rid] = init_node({
            "id": rid, "kind": kind, "parent": None, "label": label, "state": "OPEN",
            "question": str(project.get("question")
                            or f"which branch of {label} deserves the next cell?"),
            "children": [], "spec": None, "project": label, "path_labels": [label]})
        if (p := project.get("prior")) is not None:
            nodes[rid]["prior"] = _num(p, 0.5)
        tips = [rid]
        levels: Sequence[Any] = project.get("levels") or ()
        for depth, level in enumerate(levels, start=1):
            kind = depth_kinds[min(depth, len(depth_kinds) - 1)]
            nxt: list[str] = []
            for pid in tips:
                parent = nodes[pid]
                for lab in _labels_for(level, str(parent["label"])):
                    cid = node_id(kind, pid, lab)
                    if cid in nodes:
                        continue
                    nodes[cid] = init_node({
                        "id": cid, "kind": kind, "parent": pid, "label": lab, "state": "OPEN",
                        "question": f"does {label} hold through {lab}?", "children": [],
                        "spec": None, "project": label,
                        "path_labels": [*parent["path_labels"], lab]})
                    parent["children"].append(cid)
                    nxt.append(cid)
            tips = nxt
        base = dict(project.get("spec") or {})
        for tip in tips:
            trail = list(nodes[tip]["path_labels"])
            nodes[tip]["spec"] = {**base, "project": label,
                                  "branch": "/".join(trail[1:-1]), "symbol": trail[-1]}
    return nodes


@dataclass
class Project:
    """One research project the manager may spend a budget on."""

    name: str
    root_id: str
    nodes: Nodes
    generator: Spawn | None = None


def allocate(weights: Sequence[float], budget: int, *, floor: float = MIN_SHARE) -> list[int]:
    """Split `budget` by weight, with a floor per project. Largest remainder, ties by index.

    A project with no measured frontier has weight zero, and zero weight still buys the floor.
    Below one rollout per project the floor is arithmetic rather than policy: a budget cannot be
    split into more pieces than it has, and `unfunded` in the report says how many missed out.
    """
    m = len(weights)
    b = max(0, int(budget))
    if m == 0 or b == 0:
        return [0] * m
    per_floor = min(max(1, int(b * floor)), b // m) if b >= m else 0
    rest = b - per_floor * m
    w = np.array([max(0.0, _num(x)) for x in weights], dtype=float)
    if float(w.sum()) <= 0.0:
        w = np.ones(m, dtype=float)
    share = w / float(w.sum()) * float(rest)
    whole = np.floor(share).astype(np.int64)
    left = rest - int(whole.sum())
    if left > 0:
        rem = sorted((-(float(share[i]) - float(whole[i])), i) for i in range(m))
        for _, i in rem[:left]:
            whole[i] += 1
    return [per_floor + int(x) for x in whole]


def project_weight(project: Project, *, k: int = 3) -> float:
    """What a project's frontier is measurably worth: the mean of its top measured leaves."""
    rows = [r for r in frontier(project.nodes, k, root_id=project.root_id) if r["measured"]]
    return (sum(float(r["value"]) for r in rows) / len(rows)) if rows else 0.0


def experiment_manager(projects: Sequence[Project], budget: int, screen: Screen, *,
                       generator: Spawn | None = None, seed: int = 0, c_puct: float = C_PUCT,
                       penalty: Penalty | None = None, floor: float = MIN_SHARE,
                       budget_evals: int = 1, frontier_k: int = FRONTIER_K) -> dict[str, Any]:
    """Spend one budget of rollouts across several projects, and say which branches to deepen.

    The allocation is by measured frontier value WITH A FLOOR, in that order and for that reason:
    a manager allocating on value alone would hand the whole hour to whichever project happened
    to be screened first, and the projects it starved would stay unmeasured forever -- which
    reads exactly like being worthless. The floor is what stops "not yet measured" from becoming
    a permanent verdict.
    """
    weights = [project_weight(p) for p in projects]
    grants = allocate(weights, budget, floor=floor)
    rows: list[dict[str, Any]] = []
    deepen: dict[str, dict[str, Any]] = {}
    total_evals = total_blank = total_added = 0
    for i, (proj, grant, weight) in enumerate(zip(projects, grants, weights, strict=True)):
        spawn: Spawn = proj.generator or generator or (lambda _n: [])
        rep = run(proj.nodes, proj.root_id, spawn, screen, iterations=grant, seed=seed + i,
                  c_puct=c_puct, penalty=penalty, budget_evals=budget_evals,
                  frontier_k=frontier_k)
        total_evals += rep.evaluations
        total_blank += rep.unmeasured
        total_added += rep.nodes_added
        rows.append({"name": proj.name, "root_id": proj.root_id, "allocated": grant,
                     "weight": round(weight, 6), "status": rep.status,
                     "evaluations": rep.evaluations, "unmeasured": rep.unmeasured,
                     "nodes_added": rep.nodes_added,
                     "concentration": round(rep.concentration, 6), "frontier": rep.best})
        for leaf in rep.best:
            trail = list(leaf["path"])
            if not leaf["measured"] or len(trail) < 2:
                continue
            bid = str(trail[1])
            held = deepen.get(bid)
            if held is None or float(leaf["value"]) > float(held["value"]):
                deepen[bid] = {"project": proj.name, "branch_id": bid,
                               "label": str(proj.nodes[bid].get("label") or ""),
                               "kind": str(proj.nodes[bid].get("kind") or ""),
                               "value": float(leaf["value"]), "visits": visits(proj.nodes[bid]),
                               "best_leaf": leaf["id"], "spec": leaf["spec"]}
    order = sorted(deepen.values(), key=lambda r: (-float(r["value"]), str(r["branch_id"])))
    return {
        "status": "OK" if total_evals else "UNMEASURED",
        "budget": max(0, int(budget)), "floor_share": floor,
        "granted": int(sum(grants)), "unfunded": sum(1 for g in grants if g <= 0),
        "evaluations": total_evals, "unmeasured": total_blank, "nodes_added": total_added,
        "projects": rows, "deepen": order,
        "why": ("budget split across projects by measured frontier value with a floor of "
                f"{floor:.0%} each, so a project with nothing measured yet is still screened: "
                "no measured value is a gap in the evidence, not a verdict that the project is "
                "worthless. Nothing here certifies anything -- the cells these branches name "
                "face the identical ten gates."),
    }
