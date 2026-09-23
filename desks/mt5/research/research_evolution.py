"""THE META-EVOLUTION LAYER (LAWS 5m): the desk evolves its OWN research machinery under the
immutable rails -- generator configurations, search policies, cross-breeding rules,
representation grammars and the seats' prompt programs -- as a population under quality
diversity, paid in delayed real yield.

WHAT EVOLVES, AND WHAT MAY NOT. A genome here is not a strategy; it is a VARIANT OF THE RESEARCH
MACHINERY: the PUCT constant and beam the research tree searches with, the fresh-immigrant share
and refinement depth of the grammar evolution, the operator vocabulary the program IR may mutate
with, the demonstrations and decomposition a seat's prompt carries (DSPy-style: mutate the
demonstrations and the decomposition, keep what raises measured yield), the pairing rule two
populations breed under. Every proposal names the paths and symbols it reconfigures and passes
`libs/research/immutable_rails.check_change_set` BEFORE it is applied; a proposal that reaches
for the gauntlet, the trial record, a forward clock or the promotion law is refused by name and
recorded as refused. The organ also fires one deliberately rail-touching proposal at the fence on
every pass (`rails_self_test`) and applies NOTHING if that proposal is not refused -- a fence that
is not seen refusing is a fence nobody can cite.

QUALITY DIVERSITY OVER (search family x data family x region x horizon). One elite per cell, as
`qd_frontier` keeps one elite per behavioural niche and `alpha_evolution` keeps one expression per
descriptor cell (ledger G16): the archive's occupancy is published and rises as new cells are lit;
a cell's elite is displaced only by a MEASURED fitness that beats a measured incumbent. Fitness is
DELAYED REAL YIELD from `research_roi.variant_roi`: the host generator's credited survivors and
dE[log W] since the variant was activated -- never the variant's own opinion of itself, and
UNMEASURED by name until the ROI organ has credited anything. Selection carries the compute
policy's exploration and open-frontier shares (`data/compute_policy.json`, 70/20/10 by default),
so an unmeasured immigrant is still proposed, and novelty (descriptor distance to the archive) is
scored beside fitness.

CURRICULUM AND CO-EVOLUTION. New research questions are minted where the population is weakest --
the empty archive cells joined against the coverage tensor's holes and the residual hunt's open
targets -- and published for the meta-controller to price as `new_hypothesis` actions. The
adversary population (`adversary_evolution`) is read, never re-run: its dominant pathology this
hour becomes the hardening every proposal declares, so the research machinery evolves against the
moving target the gates are tested with. When a curriculum row names a representation no
installed grammar can express, or a mechanism no ontology names, the organ records a
`tool_request` / `ontology_request` discovery rather than pretending the question was askable.

EVERY APPLIED VARIANT IS A REGISTRY DISCOVERY WITH LINEAGE (parents, touches, generation) and a
row in `data/research_evolution/lineage.jsonl`, which the law-gate fence
`scripts/check_immutable_rails.py` re-checks against the rails on every commit. Nothing here has
authority over capital, gates or clocks; the consumers are the research organs that read
`active_variants.json` (research_tree, alpha_evolution, program_ir) and say which variant they ran
under.

    python desks/mt5/research/research_evolution.py --once [--budget-s 900] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import immutable_rails as IR  # noqa: E402

DATA = DESK / "data"
REPORTS = DESK / "reports"
STATE_DIR = DATA / "research_evolution"
POPULATION = STATE_DIR / "population.json"
ARCHIVE = STATE_DIR / "archive.json"
LINEAGE = STATE_DIR / "lineage.jsonl"
ACTIVE = STATE_DIR / "active_variants.json"
OUT = REPORTS / "RESEARCH_EVOLUTION.json"

ROI_REPORT = REPORTS / "RESEARCH_ROI.json"
COMPUTE_POLICY = DATA / "compute_policy.json"
COVERAGE = REPORTS / "COVERAGE_TENSOR.json"
RESIDUAL = REPORTS / "RESIDUAL_HUNT.json"
ADVERSARY_POP = DATA / "adversary_population.json"
FORGE = REPORTS / "REPRESENTATION_FORGE.json"
AXIS = REPORTS / "AXIS_REGISTRY.json"
SPECIALISATION = REPORTS / "MINER_SPECIALISATION.json"

UNMEASURED = "UNMEASURED"
BUDGET_S = 900.0
N_PROPOSALS = 12
SEED = 20260922

#: The descriptor space. `search_family` is the machinery being varied; the other three axes say
#: what the variant is pointed at, so a grammar tuned for multi-day macro bars cannot displace one
#: tuned for intrabar tape.
SEARCH_FAMILIES: tuple[str, ...] = ("mcts_tree", "grammar_evolution", "program_ir",
                                    "seat_prompt", "cross_breeding")
DATA_FAMILIES: tuple[str, ...] = ("bars", "tape", "macro", "news_events", "cross_asset",
                                  "calendar", "alt_physical")
HORIZONS: tuple[str, ...] = ("intrabar", "sub_4h", "sub_1d", "multi_day")
try:
    from research_roi import REGIONS as _ROI_REGIONS
    REGIONS: tuple[str, ...] = tuple(_ROI_REGIONS)
except Exception:
    REGIONS = ("japan", "korea", "china", "russia_cis", "south_asia", "asean", "oceania",
               "europe", "north_america", "latam", "mena", "africa", "global")

#: What each search family reconfigures (always EVOLVABLE paths), the host organ whose delayed
#: yield is the variant's fitness, and whether that host reads `active_variants.json` today.
FAMILY: dict[str, dict[str, Any]] = {
    "mcts_tree": {
        "touches": [{"path": "desks/mt5/research/research_tree.py",
                     "symbols": ["MCTS_ROOTS", "MCTS_ITER", "BEAM"]},
                    {"path": "libs/research/mcts.py", "symbols": ["C_PUCT"]}],
        "host": "research_tree", "consumer": "desks/mt5/research/research_tree.py",
        "wired": True},
    "grammar_evolution": {
        "touches": [{"path": "desks/mt5/research/alpha_evolution.py",
                     "symbols": ["FRESH_FRAC", "REFINE_TOP"]},
                    {"path": "libs/research/alpha_grammar.py", "symbols": ["mutate"]}],
        "host": "alpha_evolution", "consumer": "desks/mt5/research/alpha_evolution.py",
        "wired": True},
    "program_ir": {
        "touches": [{"path": "libs/research/program_ir.py",
                     "symbols": ["ROLLING_OPS", "BINARY_OPS", "COMPARE_OPS", "MAX_DEPTH"]}],
        "host": "program_alpha_lane", "consumer": "libs/research/program_ir.py",
        "wired": True},
    "seat_prompt": {
        "touches": [{"path": "desks/mt5/research/deepening_worker.py",
                     "symbols": ["demonstrations", "decomposition"]},
                    {"path": "libs/research/agents.py", "symbols": ["research_cycle"]}],
        "host": "deepening_worker", "consumer": "ops/*prompt*.txt (VPS-side seat prompts)",
        "wired": False},
    "cross_breeding": {
        "touches": [{"path": "libs/research/coevolution.py", "symbols": ["evolve"]},
                    {"path": "desks/mt5/research/joint_evolution.py", "symbols": ["build"]}],
        "host": "joint_evolution", "consumer": "desks/mt5/research/factor_model_coevolution.py",
        "wired": False},
}

#: The knobs a variant may move, with the closed range each lives in. Ranges are search ranges,
#: not caps on anything the desk risks: every one of them is a research-machinery parameter.
KNOBS: dict[str, dict[str, tuple[float, float]]] = {
    "mcts_tree": {"c_puct": (0.5, 3.0), "iterations": (6, 48), "roots": (1, 4),
                  "beam": (6, 24)},
    "grammar_evolution": {"fresh_frac": (0.05, 0.6), "refine_top": (2, 12), "pop": (8, 64),
                          "gens": (2, 8)},
    "program_ir": {"max_depth": (4, 10), "n_rolling": (3, 7), "n_binary": (2, 6),
                   "n_compare": (2, 4)},
    "seat_prompt": {"n_demos": (0, 6), "n_steps": (2, 7)},
    "cross_breeding": {"crossover_rate": (0.1, 0.9), "pop": (8, 32), "gens": (2, 6)},
}
INT_KNOBS = {"iterations", "roots", "beam", "refine_top", "pop", "gens", "max_depth",
             "n_rolling", "n_binary", "n_compare", "n_demos", "n_steps"}
PROGRAM_ROLLING = ("mean", "std", "max", "min", "sum", "zscore", "rank")
PROGRAM_BINARY = ("add", "sub", "mul", "div", "min2", "max2")
PROGRAM_COMPARE = ("gt", "ge", "lt", "le")
DECOMPOSITION_MENU = ("mechanism", "economic_actor", "constraint", "instrument", "horizon",
                      "session", "falsifier", "cost")
CROSS_PAIRS = (("grammar_evolution", "program_ir"), ("mcts_tree", "grammar_evolution"),
               ("program_ir", "seat_prompt"), ("mcts_tree", "program_ir"))

#: The proposal the fence MUST refuse every pass. It names the sealed gauntlet and the registry's
#: trial record: two rails the law calls out by class, chosen so the self-test can never be
#: satisfied by a rails list that forgot either.
SELF_TEST_PROPOSAL: dict[str, Any] = {
    "id": "self_test", "search_family": "mcts_tree",
    "touches": [{"path": "desks/mt5/scripts/external_gauntlet.py", "symbols": ["run"]},
                {"path": "libs/moat/registry.py", "symbols": ["record_trial"]}],
}

DEFAULT_SPLIT = {"exploitation": 0.70, "exploration": 0.20, "frontier": 0.10}


# --------------------------------------------------------------------------------- utilities
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime | None = None) -> str:
    return (t or _now()).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, doc: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        path.write_bytes(tmp.read_bytes())
        tmp.unlink(missing_ok=True)
    return path


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def _gid(*parts: Any) -> str:
    return "rev_" + hashlib.sha256(json.dumps(parts, sort_keys=True, default=str)
                                   .encode("utf-8")).hexdigest()[:12]


def cell_key(g: dict[str, Any]) -> str:
    return "|".join(str(g.get(k) or "?") for k in ("search_family", "data_family", "region",
                                                    "horizon"))


def possible_cells() -> int:
    return len(SEARCH_FAMILIES) * len(DATA_FAMILIES) * len(REGIONS) * len(HORIZONS)


# --------------------------------------------------------------------------------- genomes
def random_config(family: str, rng: random.Random) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    for knob, (lo, hi) in KNOBS[family].items():
        v = rng.uniform(lo, hi)
        cfg[knob] = round(v) if knob in INT_KNOBS else round(v, 3)
    if family == "program_ir":
        cfg["rolling_ops"] = sorted(rng.sample(PROGRAM_ROLLING, cfg["n_rolling"]))
        cfg["binary_ops"] = sorted(rng.sample(PROGRAM_BINARY, cfg["n_binary"]))
        cfg["compare_ops"] = sorted(rng.sample(PROGRAM_COMPARE, cfg["n_compare"]))
        cfg["state_machines"] = bool(rng.random() < 0.5)
    elif family == "seat_prompt":
        cfg["decomposition"] = list(rng.sample(DECOMPOSITION_MENU, cfg["n_steps"]))
        cfg["demonstration_rule"] = ("the n_demos most recent CERTIFIED cells of the seat's own "
                                     "family, quoted with their falsifier and forward R")
    elif family == "cross_breeding":
        cfg["pair"] = list(rng.choice(CROSS_PAIRS))
    return cfg


def mutate_config(family: str, cfg: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """One knob moved a bounded step; a vocabulary knob swaps one member."""
    out = json.loads(json.dumps(cfg))
    knob = rng.choice(sorted(KNOBS[family]))
    lo, hi = KNOBS[family][knob]
    step = (hi - lo) * rng.uniform(-0.25, 0.25)
    v = min(hi, max(lo, float(out.get(knob, lo)) + step))
    out[knob] = round(v) if knob in INT_KNOBS else round(v, 3)
    if family == "program_ir":
        for key, menu, n_key in (("rolling_ops", PROGRAM_ROLLING, "n_rolling"),
                                 ("binary_ops", PROGRAM_BINARY, "n_binary"),
                                 ("compare_ops", PROGRAM_COMPARE, "n_compare")):
            out[key] = sorted(rng.sample(menu, min(len(menu), int(out[n_key]))))
        if rng.random() < 0.3:
            out["state_machines"] = not bool(out.get("state_machines"))
    elif family == "seat_prompt":
        out["decomposition"] = list(rng.sample(DECOMPOSITION_MENU,
                                               min(len(DECOMPOSITION_MENU), int(out["n_steps"]))))
    return out


def cross_config(family: str, a: dict[str, Any], b: dict[str, Any],
                 rng: random.Random) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in set(a) | set(b):
        out[k] = json.loads(json.dumps(a[k] if (k in a and (k not in b or rng.random() < 0.5))
                                       else b[k]))
    return out


def hardening(adversary: Any) -> dict[str, Any]:
    """The adversary population's dominant pathology this hour, read from
    `adversary_evolution`'s own state; UNMEASURED when it has not run."""
    if not isinstance(adversary, dict) or not isinstance(adversary.get("population"), list):
        return {"status": UNMEASURED, "why": f"no adversary population at {ADVERSARY_POP}"}
    best: dict[str, Any] | None = None
    for ind in adversary["population"]:
        if not isinstance(ind, dict) or ind.get("is_control"):
            continue
        fit = ind.get("fitness")
        if isinstance(fit, (int, float)) and (best is None or fit > float(best["fitness"])):
            best = ind
    if best is None or not isinstance(best.get("genome"), dict):
        return {"status": UNMEASURED, "why": "no scored attack genome in the population"}
    genome = {k: float(v) for k, v in best["genome"].items() if isinstance(v, (int, float))}
    dominant = max(genome, key=lambda k: genome[k]) if genome else None
    return {"status": "MEASURED", "generation": adversary.get("generation"),
            "attack_id": best.get("id"), "dominant_pathology": dominant,
            "genome": genome,
            "rule": ("every proposal this pass declares the pathology it is hardened against; "
                     "the gates stay where they are -- the research machinery moves")}


def make_genome(family: str, data_family: str, region: str, horizon: str,
                cfg: dict[str, Any], parents: list[str], generation: int, kind: str,
                hard: dict[str, Any]) -> dict[str, Any]:
    gid = _gid(family, data_family, region, horizon, cfg, parents, generation)
    return {
        "id": gid, "search_family": family, "data_family": data_family, "region": region,
        "horizon": horizon, "config": cfg,
        "touches": json.loads(json.dumps(FAMILY[family]["touches"])),
        "parents": list(parents), "generation": generation, "kind": kind,
        "born": _iso(), "host": FAMILY[family]["host"],
        "hardened_against": hard.get("dominant_pathology"),
        "fitness": {"status": UNMEASURED, "value": None,
                    "basis": "research_roi.variant_roi has not credited this variant"},
        "activated_at": None,
    }


# --------------------------------------------------------------------------------- fitness
def variant_fitness(roi: Any) -> dict[str, dict[str, Any]]:
    """`research_roi.variant_roi`, keyed by variant id: the delayed real yield of the host
    generator since activation. Absent = every variant UNMEASURED."""
    if not isinstance(roi, dict) or not isinstance(roi.get("variant_roi"), dict):
        return {}
    block = roi["variant_roi"]
    rows = block.get("variants") if isinstance(block.get("variants"), dict) else {}
    return {str(k): v for k, v in rows.items() if isinstance(v, dict)}


def novelty(g: dict[str, Any], archive: dict[str, Any]) -> float:
    """Descriptor distance to the nearest archived elite (0 = its cell is filled, 1 = nothing in
    the archive shares any axis with it)."""
    cells = archive.get("cells") if isinstance(archive.get("cells"), dict) else {}
    if not cells:
        return 1.0
    mine = cell_key(g).split("|")
    best = 0
    for key in cells:
        parts = key.split("|")
        best = max(best, sum(1 for a, b in zip(mine, parts, strict=False) if a == b))
    return round(1.0 - best / 4.0, 3)


def split_from_policy(policy: Any) -> tuple[dict[str, float], str]:
    if isinstance(policy, dict) and isinstance(policy.get("split"), dict):
        s = {k: float(v) for k, v in policy["split"].items() if isinstance(v, (int, float))}
        if all(k in s for k in DEFAULT_SPLIT) and abs(sum(s.values()) - 1.0) < 1e-6:
            return {k: s[k] for k in DEFAULT_SPLIT}, (f"data/compute_policy.json "
                                                       f"({policy.get('status')})")
    return dict(DEFAULT_SPLIT), "default 70/20/10 -- compute_policy.json absent or unreadable"


# --------------------------------------------------------------------------------- curriculum
def weakest_cells(archive: dict[str, Any], rng: random.Random, n: int) -> list[dict[str, str]]:
    """Empty descriptor cells, sampled -- the population is weakest where it has never been."""
    cells = archive.get("cells") if isinstance(archive.get("cells"), dict) else {}
    out: list[dict[str, str]] = []
    tries = 0
    while len(out) < n and tries < 400:
        tries += 1
        g = {"search_family": rng.choice(SEARCH_FAMILIES), "data_family": rng.choice(DATA_FAMILIES),
             "region": rng.choice(REGIONS), "horizon": rng.choice(HORIZONS)}
        if cell_key(g) not in cells and g not in out:
            out.append(g)
    return out


def _installed_representations(forge: Any) -> set[str]:
    reps: set[str] = set(PROGRAM_ROLLING) | set(PROGRAM_BINARY) | {
        "open", "high", "low", "close", "ret", "range", "body", "tr", "atr"}
    if isinstance(forge, dict):
        for key in ("families", "representations"):
            v = forge.get(key)
            if isinstance(v, dict):
                reps |= {str(k).lower() for k in v}
            elif isinstance(v, list):
                reps |= {str(r.get("family") or r.get("id") or r).lower()
                         for r in v if isinstance(r, (dict, str))}
    return reps


def _known_mechanisms(axis: Any) -> set[str]:
    if not isinstance(axis, dict):
        return set()
    out: set[str] = set()
    for key in ("mechanisms", "vocabulary", "axes"):
        v = axis.get(key)
        if isinstance(v, dict):
            m = v.get("mechanism") if isinstance(v.get("mechanism"), (list, dict)) else v
            out |= {str(x).lower() for x in (m if isinstance(m, (list, dict)) else [])}
        elif isinstance(v, list):
            out |= {str(x).lower() for x in v}
    return out


def curriculum(archive: dict[str, Any], coverage: Any, residual: Any, forge: Any, axis: Any,
               spec: Any, rng: random.Random, n: int = 12) -> tuple[list[dict[str, Any]],
                                                                    list[dict[str, Any]]]:
    """Research questions where the population is weakest, joined with the coverage holes and
    the residual targets -- plus the tool/ontology requests those questions expose."""
    questions: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    reps = _installed_representations(forge)
    mechs = _known_mechanisms(axis)
    holes: list[dict[str, Any]] = []
    if isinstance(coverage, dict) and isinstance(coverage.get("frontier"), dict):
        top = coverage["frontier"].get("top")
        holes = [h for h in (top or []) if isinstance(h, dict)]
    targets: list[dict[str, Any]] = []
    if isinstance(residual, dict) and isinstance(residual.get("targets"), list):
        targets = [t for t in residual["targets"] if isinstance(t, dict)]
    weak: list[str] = []
    try:
        from miner_specialisation import weak_domains
        weak = weak_domains(spec if isinstance(spec, dict) else {}, 6)
    except Exception:
        weak = []
    for cell in weakest_cells(archive, rng, n):
        hole = holes[rng.randrange(len(holes))] if holes else None
        target = targets[rng.randrange(len(targets))] if targets else None
        q = {
            "cell": cell,
            "question": (f"what {cell['search_family']} variant, pointed at {cell['data_family']} "
                         f"data in {cell['region']} at the {cell['horizon']} horizon, produces an "
                         f"independent survivor"),
            "why": "no variant in the archive has ever occupied this descriptor cell",
            "coverage_hole": hole, "residual_target": (target or {}).get("cluster_id"),
            "weak_miner_domains": weak,
            "source": "research_evolution",
        }
        questions.append(q)
        if hole is not None:
            rep = str(hole.get("representation") or "").lower()
            if rep and rep not in reps:
                requests.append({"kind": "tool_request", "what": rep,
                                 "why": (f"coverage hole asks for representation {rep!r}, which "
                                         f"no installed grammar or forge family can express"),
                                 "cell": cell, "hole": hole})
            mech = str(hole.get("mechanism") or "").lower()
            if mech and mechs and mech not in mechs:
                requests.append({"kind": "ontology_request", "what": mech,
                                 "why": (f"coverage hole names mechanism {mech!r}, which the axis "
                                         f"registry's ontology does not carry"),
                                 "cell": cell, "hole": hole})
    # a residual target whose explanation names a dataset the desk has no representation for
    for t in targets[:20]:
        expl = t.get("candidate_explanations") if isinstance(t.get("candidate_explanations"),
                                                             dict) else {}
        for ds in (expl.get("missing_dataset") or [])[:2]:
            name = str(ds.get("text") if isinstance(ds, dict) else ds)
            if name and name.lower() not in reps:
                requests.append({"kind": "tool_request", "what": name,
                                 "why": (f"residual target {t.get('cluster_id')} needs "
                                         f"{name!r}, which no installed representation ingests"),
                                 "residual_target": t.get("cluster_id")})
                break
    # dedupe requests on (kind, what)
    seen: set[tuple[str, str]] = set()
    uniq: list[dict[str, Any]] = []
    for r in requests:
        k = (r["kind"], r["what"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return questions, uniq


# --------------------------------------------------------------------------------- the pass
def propose(population: dict[str, Any], archive: dict[str, Any], split: dict[str, float],
            hard: dict[str, Any], rng: random.Random, n: int) -> list[dict[str, Any]]:
    """`n` proposals in the policy's shares: exploit (mutate a measured elite), explore (cross two
    elites), frontier (an immigrant into an empty cell)."""
    genomes: list[dict[str, Any]] = [g for g in population.get("genomes", [])
                                     if isinstance(g, dict)]
    gen = int(population.get("generation") or 0) + 1
    measured = [g for g in genomes if g.get("fitness", {}).get("status") == "MEASURED"]
    measured.sort(key=lambda g: -float(g["fitness"].get("value") or 0.0))
    n_exploit = round(n * split["exploitation"])
    n_explore = round(n * split["exploration"])
    n_frontier = max(0, n - n_exploit - n_explore)
    out: list[dict[str, Any]] = []
    # exploitation: needs a measured elite; otherwise the share is spent as exploration of the
    # existing (unmeasured) population, which is the honest thing to do with no yield yet
    pool = measured or genomes
    for _ in range(n_exploit):
        if not pool:
            break
        parent = rng.choice(pool[: max(1, len(pool) // 2)])
        fam = str(parent["search_family"])
        out.append(make_genome(fam, str(parent["data_family"]), str(parent["region"]),
                               str(parent["horizon"]), mutate_config(fam, parent["config"], rng),
                               [str(parent["id"])], gen,
                               "mutation" if measured else "mutation_unmeasured", hard))
    for _ in range(n_explore):
        if len(genomes) < 2:
            break
        a, b = rng.sample(genomes, 2)
        if a["search_family"] != b["search_family"]:
            b = a
        fam = str(a["search_family"])
        out.append(make_genome(fam, str(rng.choice((a["data_family"], b["data_family"]))),
                               str(rng.choice((a["region"], b["region"]))),
                               str(rng.choice((a["horizon"], b["horizon"]))),
                               cross_config(fam, a["config"], b["config"], rng),
                               sorted({str(a["id"]), str(b["id"])}), gen, "crossover", hard))
    n_frontier += (n_exploit + n_explore) - len(out)
    for cell in weakest_cells(archive, rng, n_frontier):
        fam = cell["search_family"]
        out.append(make_genome(fam, cell["data_family"], cell["region"], cell["horizon"],
                               random_config(fam, rng), [], gen, "immigrant", hard))
    return out


def archive_put(archive: dict[str, Any], g: dict[str, Any]) -> bool:
    """One elite per cell: an empty cell is filled; a measured fitness displaces an unmeasured or
    a weaker measured incumbent; an unmeasured newcomer never displaces anything."""
    cells = archive.setdefault("cells", {})
    key = cell_key(g)
    fit = g.get("fitness") or {}
    measured = fit.get("status") == "MEASURED"
    value = float(fit.get("value") or 0.0) if measured else None
    have = cells.get(key)
    if have is None:
        cells[key] = {"genome_id": g["id"], "fitness": value, "measured": measured,
                      "since": _iso()}
        return True
    if not measured:
        return False
    if not have.get("measured") or float(have.get("fitness") or 0.0) < float(value or 0.0):
        cells[key] = {"genome_id": g["id"], "fitness": value, "measured": True, "since": _iso()}
        return True
    return False


def _record_discovery(g: dict[str, Any], verdict: dict[str, Any]) -> tuple[str | None, str]:
    try:
        from libs.moat import registry as reg
        did, created = reg.record_discovery(
            source_id="research_evolution", source_type="research_variant",
            mechanism=(f"{g['search_family']} variant for {g['data_family']}/{g['region']}/"
                       f"{g['horizon']}: {json.dumps(g['config'], sort_keys=True)[:160]}"),
            origin="DESK", generator=f"research_evolution:{g['id']}", discovery_id=g["id"],
            kind="research_variant", parent_ids=list(g.get("parents") or []),
            assets=[], horizons=[g["horizon"]], regimes=[], sessions=[],
            information=g["data_family"], novelty=1.0, confidence=0.5,
            economic_rationale=("a research-machinery variant; its value is the delayed yield "
                                "of the host generator it configures"),
            falsifier=("research_roi.variant_roi credits it no survivor and no dE[log W] over "
                       "its activation window while a sibling variant is credited"),
            payload={"genome": g, "rails_verdict": verdict})
        return did, "created" if created else "existing"
    except Exception as exc:
        return None, f"registry unavailable: {type(exc).__name__}: {exc}"


def _record_request(r: dict[str, Any]) -> tuple[str | None, str]:
    try:
        from libs.moat import registry as reg
        did, created = reg.record_discovery(
            source_id="research_evolution", source_type=str(r["kind"]),
            mechanism=f"{r['kind']}: {r['what']}", origin="DESK",
            generator="research_evolution", kind=str(r["kind"]), assets=[],
            economic_rationale=str(r.get("why") or ""), novelty=1.0, confidence=0.3,
            required_data=[r["what"]] if r["kind"] == "tool_request" else [],
            falsifier="an installed representation or ontology term expresses the mechanism",
            payload=r)
        return did, "created" if created else "existing"
    except Exception as exc:
        return None, f"registry unavailable: {type(exc).__name__}: {exc}"


def active_variants(population: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    """Per search family, the variant the consumers should run under: the best MEASURED elite,
    else the newest applied genome (exploration, and said so)."""
    by_id = {str(g["id"]): g for g in population.get("genomes", []) if isinstance(g, dict)}
    out: dict[str, Any] = {}
    cells = archive.get("cells") if isinstance(archive.get("cells"), dict) else {}
    for fam in SEARCH_FAMILIES:
        best: dict[str, Any] | None = None
        for key, row in cells.items():
            if not key.startswith(fam + "|") or not row.get("measured"):
                continue
            g = by_id.get(str(row.get("genome_id")))
            if g and (best is None or float(row.get("fitness") or 0.0)
                      > float(best["fitness"].get("value") or 0.0)):
                best = g
        basis = "best measured elite"
        if best is None:
            cands = [g for g in by_id.values() if g.get("search_family") == fam]
            cands.sort(key=lambda g: str(g.get("born") or ""))
            best = cands[-1] if cands else None
            basis = "newest applied genome (no measured elite yet: exploration)"
        if best is None:
            continue
        out[fam] = {"id": best["id"], "config": best["config"], "basis": basis,
                    "consumer": FAMILY[fam]["consumer"], "wired": FAMILY[fam]["wired"],
                    "activated_at": best.get("activated_at") or _iso()}
    return out


def run(*, budget_s: float = BUDGET_S, dry_run: bool = False,
        n_proposals: int = N_PROPOSALS, seed: int | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = _now()
    rng = random.Random(seed if seed is not None else SEED + int(now.timestamp()) // 3600)  # noqa: S311
    unmeasured: list[dict[str, str]] = []

    population = _read(POPULATION) or {"generation": 0, "genomes": []}
    if not isinstance(population, dict):
        population = {"generation": 0, "genomes": []}
    archive = _read(ARCHIVE) or {"cells": {}}
    if not isinstance(archive, dict):
        archive = {"cells": {}}
    occupancy_before = len(archive.get("cells") or {})

    # THE FENCE IS SEEN REFUSING BEFORE ANYTHING IS APPLIED.
    self_test = IR.refuse_proposal(SELF_TEST_PROPOSAL)
    rails_ok = not self_test.ok and len(self_test.refused) >= 2
    if not rails_ok:
        doc = {"at": _iso(now), "status": "BLOCKED",
               "why": ("the rails self-test proposal (external_gauntlet.py::run + "
                       "registry.py::record_trial) was NOT refused; nothing is applied until the "
                       "fence is seen refusing it"),
               "rails_self_test": self_test.as_dict(), "dry_run": dry_run}
        if not dry_run:
            _atomic_write(OUT, doc)
        return doc

    roi = _read(ROI_REPORT)
    fitness = variant_fitness(roi)
    if not fitness:
        unmeasured.append({"what": "variant fitness",
                           "why": f"{ROI_REPORT.name} carries no variant_roi block yet; every "
                                  f"genome's fitness is UNMEASURED and nothing is displaced"})
    n_measured = 0
    for g in population.get("genomes", []):
        row = fitness.get(str(g.get("id")))
        if row and row.get("status") == "MEASURED" and isinstance(row.get("value"), (int, float)):
            g["fitness"] = {"status": "MEASURED", "value": float(row["value"]),
                            "basis": str(row.get("basis") or "research_roi.variant_roi")}
            n_measured += 1
            archive_put(archive, g)

    split, split_basis = split_from_policy(_read(COMPUTE_POLICY))
    hard = hardening(_read(ADVERSARY_POP))
    if hard.get("status") != "MEASURED":
        unmeasured.append({"what": "adversary pressure", "why": str(hard.get("why"))})

    proposals = propose(population, archive, split, hard, rng, n_proposals)
    applied: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    lit = 0
    for g in proposals:
        if time.monotonic() - t0 > budget_s:
            unmeasured.append({"what": "proposals", "why": f"budget {budget_s}s reached; "
                                                            f"{len(proposals)} proposed, "
                                                            f"{len(applied) + len(refused)} "
                                                            f"judged"})
            break
        verdict = IR.refuse_proposal(g)
        g["novelty"] = novelty(g, archive)
        row = {"id": g["id"], "parents": g["parents"], "touches": g["touches"],
               "search_family": g["search_family"], "cell": cell_key(g), "kind": g["kind"],
               "at": _iso(), "applied": verdict.ok,
               "refused": [r.as_dict() for r in verdict.refused]}
        if not verdict.ok:
            refused.append(row)
            if not dry_run:
                _append_jsonl(LINEAGE, row)
            continue
        g["activated_at"] = _iso()
        population.setdefault("genomes", []).append(g)
        if archive_put(archive, g):
            lit += 1
        if not dry_run:
            did, how = _record_discovery(g, verdict.as_dict())
            row["discovery_id"], row["registry"] = did, how
            _append_jsonl(LINEAGE, row)
        applied.append(row)
    population["generation"] = int(population.get("generation") or 0) + (1 if applied else 0)
    population["updated"] = _iso()

    questions, requests = curriculum(archive, _read(COVERAGE), _read(RESIDUAL), _read(FORGE),
                                     _read(AXIS), _read(SPECIALISATION), rng)
    if not dry_run:
        for r in requests:
            r["discovery_id"], r["registry"] = _record_request(r)

    active = active_variants(population, archive)
    occupancy_after = len(archive.get("cells") or {})
    archive["possible"] = possible_cells()
    archive["updated"] = _iso()
    doc = {
        "at": _iso(now), "law": "LAWS 5m -- the meta-evolution layer under the immutable rails",
        "status": "OK", "dry_run": dry_run, "budget_s": budget_s,
        "elapsed_s": round(time.monotonic() - t0, 2),
        "rails_self_test": {"refused": True,
                            "by": [f"{r.path}::{r.symbol}" for r in self_test.refused]},
        "population": {"generation": population["generation"],
                       "n": len(population.get("genomes", [])),
                       "n_measured": n_measured,
                       "by_family": {f: sum(1 for g in population.get("genomes", [])
                                            if g.get("search_family") == f)
                                     for f in SEARCH_FAMILIES}},
        "archive": {"occupancy": occupancy_after, "possible": possible_cells(),
                    "share": round(occupancy_after / possible_cells(), 4),
                    "lit_this_pass": lit, "occupancy_before": occupancy_before,
                    "axes": {"search_family": list(SEARCH_FAMILIES),
                             "data_family": list(DATA_FAMILIES), "region": list(REGIONS),
                             "horizon": list(HORIZONS)}},
        "selection": {"split": split, "basis": split_basis,
                      "novelty": "descriptor distance to the nearest archived elite"},
        "fitness": {"basis": "research_roi.variant_roi -- host generator's credited survivors "
                             "and dE[log W] since activation (delayed real yield)",
                    "n_variants_credited": len(fitness)},
        "proposals": {"n": len(proposals), "applied": applied, "refused": refused},
        "active_variants": active,
        "consumers": {f: {"consumer": FAMILY[f]["consumer"], "host": FAMILY[f]["host"],
                          "wired": FAMILY[f]["wired"],
                          "note": ("reads active_variants.json" if FAMILY[f]["wired"] else
                                   "UNWIRED: the surface is not on this box; the variant is "
                                   "published and the gap is named")}
                      for f in SEARCH_FAMILIES},
        "coevolution": hard,
        "curriculum": questions,
        "requests": requests,
        "unmeasured": unmeasured,
        "rule": ("every proposal passes immutable_rails before it is applied; every applied one "
                 "is a registry discovery with lineage; fitness is delayed real yield, never the "
                 "variant's own score; the archive keeps one elite per descriptor cell"),
    }
    if not dry_run:
        _atomic_write(POPULATION, population)
        _atomic_write(ARCHIVE, archive)
        _atomic_write(ACTIVE, {"at": _iso(), "variants": active,
                               "writer": "desks/mt5/research/research_evolution.py"})
        _atomic_write(OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--proposals", type=int, default=N_PROPOSALS)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run, n_proposals=a.proposals)
    if doc.get("status") != "OK":
        print(f"research evolution: {doc.get('status')} -- {doc.get('why')}")
        return 1
    arc = doc["archive"]
    print(f"research evolution: gen {doc['population']['generation']}, "
          f"{doc['population']['n']} genomes ({doc['population']['n_measured']} measured); "
          f"archive {arc['occupancy']}/{arc['possible']} (+{arc['lit_this_pass']}); "
          f"applied {len(doc['proposals']['applied'])}, refused "
          f"{len(doc['proposals']['refused'])}; {len(doc['curriculum'])} questions, "
          f"{len(doc['requests'])} requests"
          + ("; DRY RUN, nothing written" if a.dry_run else f" -> {OUT}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
