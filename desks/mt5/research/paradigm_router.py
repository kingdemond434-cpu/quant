"""THE PARADIGM ROUTER -- every lead meets every discovery paradigm, and the arguments are kept.

THE PRINCIPAL, 2026-09-17 (ledger item M14): "independent parallel discovery paradigms -- every
lead fed to LLM, MCTS, MAP-Elites, GFlowNet, GP, symbolic regression, Bayesian search, program
evolution and causal discovery; method agreement and disagreement recorded per lead."

WHAT WAS THERE BEFORE, AND WHY IT IS A MONOCULTURE. Nine paradigms exist on this desk, each a
fine separate organ on its own clock, and a lead reaches AT MOST ONE of them -- whichever miner
happened to find it. A claim mined by a seat goes to the seats' compiler and nowhere else; the
causal lab never hears of it, MCTS never projects it onto an instrument, no population ever draws
its shape. So the desk owns nine ways of being wrong and uses one per lead, which is the failure
`search_populations` names for samplers one level down: three samplers over one grammar is still
ONE search, because they fail the same way. The router is the other half of that argument: one
lead, nine attempts, by methods that fail differently.

AGREEMENT IS USEFUL. DISAGREEMENT IS VALUABLE, AND IT IS THE OUTPUT NOTHING ELSE PRODUCES. When
the causal lab has an admitted edge on the instrument a language model reasoned its way to, that
is two independent methods on one claim and the prior should move. When MCTS projects a mechanism
onto metals and MAP-Elites refuses the same niche, THAT IS A FINDING -- it names an assumption
one of them is making that the other is not, and a single-paradigm pipeline can never produce it
because there is nothing to disagree with. Every disagreement is written to the registry as
`research_memory` kind `method_disagreement`, keyed by the lead, so it outlives the pass.

WHAT IS STEERABLE TODAY, SAID PLAINLY RATHER THAN IMPLIED (and published as `gaps`). Seven of the
nine take a lead directly: the LLM seats (a row under `data/intelligence/`, which both compilers
glob), MCTS (`project_tree` builds the whole project from the lead), MAP-Elites
(`qd_frontier.proposal` is a pure function of a niche) and the four populations
(`search_populations.run` takes a context). Two do not: `program_alpha_lane` seeds from its own
template library and the top-scoring rows of its program database -- a fresh row scores `-inf`
and is never drawn -- and `causal_lab` recomputes its panel from bars, so a lead can only be
CHECKED against its artifact, never fed into it. Those two are reported as what they are. Naming
the gap is the work; pretending the feed happened would make the coverage number a lie.

    python paradigm_router.py --dry-run          # measure and print; write nothing, record nothing
    python paradigm_router.py --max-leads 50 --budget-s 240
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
for _p in (str(REPO), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "PARADIGM_ROUTER.json"
INTAKE = DESK / "data" / "intelligence" / "paradigm_router"
CAUSAL_LAB = DESK / "reports" / "CAUSAL_LAB.json"

MAX_LEADS = 50
BUDGET_S = 240.0
#: Trees one call of the four populations draws per lead. Small on purpose: this router measures
#: WHETHER a paradigm can speak about a lead, not how much it can say -- the paradigms' own
#: clocks do the volume, and a router that out-drew them would be a tenth search nobody asked for.
DRAWS_PER_POPULATION = 4
MCTS_ITERATIONS = 8
FRONTIER_K = 6

POPULATIONS: tuple[str, ...] = ("gflownet", "gp", "symreg", "bayesian")
PARADIGMS: tuple[str, ...] = ("llm_seats", "mcts", "map_elites", *POPULATIONS,
                              "program_evolution", "causal_discovery")

#: paradigm key -> the module that owns it. `_load` is the ONE import door, so a test stands in
#: for the whole desk by monkeypatching it and nothing here imports behind its back.
MODULES: dict[str, str] = {
    "mcts": "libs.research.mcts",
    "map_elites": "qd_frontier",
    "populations": "libs.research.search_populations",
    "program_evolution": "program_alpha_lane",
    "axis": "axis_registry",
}

RULE = ("no LLM monoculture: every lead meets every paradigm; agreement is useful, disagreement "
        "is valuable")

_LOADED: dict[str, tuple[Any, str]] = {}


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _load(key: str) -> tuple[Any, str]:
    """Import one paradigm's module once. Returns (module, why) -- (None, reason) on failure.

    A PARADIGM THAT CANNOT BE IMPORTED IS UNAVAILABLE, NOT ABSENT OF VALUE. The reason is carried
    all the way to the report, because "pandas is missing on this box" and "this desk has no
    causal lab" are different facts and a bare False renders them identically.
    """
    if key in _LOADED:
        return _LOADED[key]
    dotted = MODULES.get(key, key)
    try:
        mod = __import__(dotted, fromlist=["*"])
        out = (mod, "")
    except Exception as exc:
        out = (None, f"{dotted} unavailable: {type(exc).__name__}: {exc}")
    _LOADED[key] = out
    return out


def _j(raw: Any, default: Any) -> Any:
    if isinstance(raw, (list, dict)):
        return raw
    try:
        val = json.loads(raw) if isinstance(raw, str) and raw.strip() else default
    except ValueError:
        return default
    return val if isinstance(val, type(default)) else default


def _syms(raw: Any) -> list[str]:
    return [str(s).strip().upper() for s in _j(raw, []) if str(s).strip()][:6]


# --------------------------------------------------------------------------- the leads
def leads(max_leads: int = MAX_LEADS) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Every lead worth routing: interpreted/expanded discoveries with a mechanism, then the
    best-scored queued candidates. Deduped on (mechanism, family, first instrument), because two
    names for one claim would double every paradigm's work and every agreement count.
    """
    unmeasured: list[dict[str, str]] = []
    try:
        from libs.moat import registry as reg
    except Exception as exc:
        return [], [{"what": "registry", "why": f"{type(exc).__name__}: {exc}"}]
    rows: list[dict[str, Any]] = []
    try:
        for state in ("INTERPRETED", "EXPANDED"):
            for d in reg.discoveries(state=state, limit=max_leads * 2):
                mech = str(d.get("mechanism") or "").strip()
                if not mech:
                    continue
                rule = _j(d.get("exact_rule"), {})
                params = rule.get("params") if isinstance(rule.get("params"), dict) else {}
                rows.append({
                    "lead_id": str(d.get("discovery_id")), "kind": "discovery",
                    "discovery_id": str(d.get("discovery_id")), "state": state,
                    "mechanism": mech,
                    "family": str(rule.get("family") or d.get("generator") or ""),
                    "symbols": _syms(d.get("assets_json")), "params": params,
                    "session": (_syms(d.get("sessions_json")) or ["all"])[0].lower(),
                    "horizon": (_syms(d.get("horizons_json")) or [""])[0].lower(),
                    "regime": (_syms(d.get("regimes_json")) or [""])[0].lower(),
                    "direction": str(params.get("direction") or "").lower() or None,
                    "why": str(d.get("economic_rationale") or "")[:200],
                    "score": float(d.get("confidence") or 0.0)})
    except Exception as exc:
        unmeasured.append({"what": "discoveries", "why": f"{type(exc).__name__}: {exc}"})
    try:
        for c in reg.candidates(status="queued", limit=max_leads * 2):
            params = _j(c.get("params_json"), {})
            rows.append({
                "lead_id": str(c.get("id")), "kind": "candidate",
                "discovery_id": str(c.get("discovery_id") or c.get("id")), "state": "QUEUED",
                "mechanism": str(c.get("mechanism") or "").strip(),
                "family": str(c.get("family") or ""), "symbols": _syms([c.get("symbol")]),
                "params": params, "session": str(c.get("session") or "all").lower(),
                "horizon": str(c.get("horizon") or "").lower(),
                "regime": str(c.get("regime") or "").lower(),
                "direction": str(params.get("direction") or "").lower() or None,
                "why": str(c.get("causal_rationale") or "")[:200],
                "score": float(c.get("score") or 0.0)})
    except Exception as exc:
        unmeasured.append({"what": "candidates", "why": f"{type(exc).__name__}: {exc}"})
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for r in sorted(rows, key=lambda x: (-float(x["score"]), str(x["lead_id"]))):
        key = (r["mechanism"], r["family"], (r["symbols"] or [""])[0])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= max_leads:
            break
    return out, unmeasured


def _outcome(name: str, status: str, why: str, *, produced: int = 0,
             instruments: list[str] | None = None, direction: str | None = None,
             detail: Any = None) -> dict[str, Any]:
    """One paradigm's verdict on one lead. `status` is the vocabulary the report counts:
    PRODUCED, NONE (it spoke and produced nothing), UNMEASURED (it ran and could not measure),
    GAP (it has no intake for this lead) or UNAVAILABLE (the module could not be imported)."""
    return {"paradigm": name, "status": status, "produced": int(produced),
            "instruments": sorted({str(s).upper() for s in (instruments or [])}),
            "direction": direction, "why": why, "detail": detail}


# --------------------------------------------------------------------------- the nine paradigms
def p_llm_seats(lead: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """The LLM seats, through the intake both compilers already read.

    `discovery_compiler` globs `data/intelligence/*/*.json` and `miner_candidate_compiler`
    rglobs the same tree, so a row written under `paradigm_router/` is picked up by the desk's
    existing machinery with no new wiring. A lead that carries a registered family and an
    instrument goes as a STRUCTURED_HYPOTHESIS row; one that does not goes as a QUESTION with
    the mechanism spelled out, because a seat can answer a question and a compiler cannot
    execute a guess.
    """
    fam, syms = str(lead.get("family") or ""), list(lead.get("symbols") or [])
    row: dict[str, Any] = {
        "lead_id": lead["lead_id"], "discovery_id": lead["discovery_id"],
        "mechanism": lead["mechanism"], "source": "paradigm_router",
        "why": lead.get("why") or f"routed lead on {lead['mechanism']}",
        "prompt": (f"Mechanism: {lead['mechanism']}. Who is forced to pay, on what instrument of "
                   f"the MT5/Fusion universe, in which session, and what exact rule would test "
                   f"it? Name the falsifier. Lead state {lead['state']}"
                   + (f"; declared instruments {', '.join(syms)}" if syms else
                      "; NO instrument declared -- name the ones the mechanism implies")),
    }
    if fam and syms:
        row.update({"kind": "hypothesis", "family": fam, "symbols": syms,
                    "params": lead.get("params") or {}})
        return _outcome("llm_seats", "PRODUCED", "structured hypothesis row for the seat intake",
                        produced=1, instruments=syms, direction=lead.get("direction"),
                        detail={"kind": "hypothesis", "family": fam}), row
    row["kind"] = "question"
    row["symbols"] = syms
    return _outcome("llm_seats", "PRODUCED",
                    "question row: the lead carries no registered family and/or no instrument, so "
                    "it reaches the seats as a question rather than an executable hypothesis",
                    produced=1, instruments=syms, direction=lead.get("direction"),
                    detail={"kind": "question"}), row


def _tree_screen() -> tuple[Any, str]:
    """`research_tree`'s cheap in-sample screen, if it exposes one at module level.

    IT DOES NOT, TODAY, and that is the finding rather than a reason to invent one. The screen
    `research_tree.build()` uses is a CLOSURE over its own loaded tree and its base rate, so it
    cannot be reached from outside without loading that tree. A screen this router made up would
    rank branches on a number nothing measured -- so the search runs with NO screen, every
    rollout returns None, and `mcts.run` reports UNMEASURED, which updates nothing and prunes
    nothing (L1.28a). The PROJECTION is still real: the leaves are instrument-level cells.
    """
    mod, why = _load("research_tree")
    if mod is None:
        return None, why
    fn = getattr(mod, "screen", None) or getattr(mod, "cheap_screen", None)
    if callable(fn):
        return fn, ""
    return None, ("research_tree exposes no module-level screen (its rollout is a closure inside "
                  "build() over the loaded tree and base rate); the search runs unscreened and "
                  "reports UNMEASURED rather than scoring a branch on an invented number")


def p_mcts(lead: dict[str, Any], *, iterations: int = MCTS_ITERATIONS) -> dict[str, Any]:
    """MCTS: project mechanism -> asset class -> instrument, then spend a bounded search on it."""
    mod, why = _load("mcts")
    if mod is None:
        return _outcome("mcts", "UNAVAILABLE", why)
    syms = list(lead.get("symbols") or [])
    if not syms:
        return _outcome("mcts", "GAP", "the lead declares no instrument, so the project's deepest "
                                       "level -- which is the instrument level by contract -- "
                                       "cannot be built")
    ax, _ = _load("axis")
    by_class: dict[str, list[str]] = {}
    for s in syms:
        klass = str(ax.asset_class_of(s)) if ax is not None else "unknown"
        by_class.setdefault(klass, []).append(s)
    root = {"label": lead["mechanism"] or "mechanism",
            "question": f"which branch of {lead['mechanism']} deserves the next cell?",
            "prior": min(1.0, max(0.0, float(lead.get("score") or 0.5))),
            "spec": {"family": lead.get("family") or "", "mechanism": lead["mechanism"],
                     "session": lead.get("session") or "all"},
            "levels": [sorted(by_class), by_class]}
    kinds = ("mechanism", "asset_class", "instrument")
    try:
        nodes = mod.project_tree([root], kinds)
        root_id = mod.node_id(kinds[0], None, str(root["label"]))
        screen, screen_why = _tree_screen()
        rep = mod.run(nodes, root_id, lambda _n: [], screen or (lambda _n: None),
                      iterations=int(iterations), seed=abs(hash(lead["lead_id"])) % (2**31),
                      frontier_k=FRONTIER_K)
    except Exception as exc:
        return _outcome("mcts", "NONE", f"{type(exc).__name__}: {exc}")
    doc = rep.to_dict() if hasattr(rep, "to_dict") else dict(rep)
    leaves = [row for row in (doc.get("frontier") or []) if row.get("id")]
    picked = [str((nodes.get(str(r["id"])) or {}).get("spec", {}).get("symbol") or "")
              for r in leaves]
    picked = [p for p in picked if p]
    status = "UNMEASURED" if str(doc.get("status")) == "UNMEASURED" else "PRODUCED"
    note = (f"{len(leaves)} instrument-level leaf/leaves projected over {len(by_class)} asset "
            f"class(es); {doc.get('evaluations', 0)} measured rollout(s)")
    return _outcome("mcts", status if picked else "NONE",
                    note + ("" if not screen_why else f". {screen_why}"),
                    produced=len(picked), instruments=picked, direction=None,
                    detail={"status": doc.get("status"), "nodes": len(nodes),
                            "unmeasured_rollouts": doc.get("unmeasured"),
                            "concentration": doc.get("concentration")})


def p_map_elites(lead: dict[str, Any]) -> dict[str, Any]:
    """MAP-Elites: the lead's behavioural niche, and the intake row that niche would donate.

    `qd_frontier.proposal` is a PURE FUNCTION of (niche, family, symbols, worker) and returns a
    row in `axis_registry`'s exact shape or None with the niche unbuildable -- so this half of
    the lane is genuinely steerable from a lead. The other half is not: `build()` recomputes its
    niches from the axis registry and the gate ledger every pass and has no seed inbox, so the
    row produced here reaches the QD map only by being judged like any other candidate. That is
    the gap, and it is reported rather than papered over.
    """
    mod, why = _load("map_elites")
    if mod is None:
        return _outcome("map_elites", "UNAVAILABLE", why)
    if getattr(mod, "ar", None) is None:
        return _outcome("map_elites", "UNAVAILABLE",
                        "qd_frontier loaded without axis_registry: niches cannot be built")
    ax = mod.ar
    syms = [s for s in (lead.get("symbols") or []) if ax.may_hypothesise(s)][:3]
    fam = str(lead.get("family") or "")
    mech, info, _style = ax.classify_family(fam) if fam else (lead["mechanism"], "", "")
    cell = {"mechanism": mech or lead["mechanism"], "information_source": info,
            "asset_class": ax.asset_class_of(syms[0]) if syms else "",
            "horizon": lead.get("horizon") or "sub_4h", "session": lead.get("session") or "all",
            "regime": lead.get("regime") or "unconditional",
            "economic_actor": ax.MECHANISM_ACTOR.get(mech or lead["mechanism"], "")}
    try:
        niche = mod.niche_of(cell)
        key = mod.niche_key(niche)
        row = mod.proposal(niche, fam or None, syms, "paradigm_router",
                           f"paradigm_router lead {lead['lead_id']}: {lead['mechanism']}",
                           float(lead.get("score") or 0.0))
    except Exception as exc:
        return _outcome("map_elites", "NONE", f"{type(exc).__name__}: {exc}")
    if row is None:
        missing = []
        if not fam:
            missing.append("no registered family")
        if not syms:
            missing.append("no hypothesis-lane instrument (the event lane reaches nothing here)")
        if mod.UNKNOWN in (niche.get("mechanism"), niche.get("information_source")):
            missing.append("an unnamed mechanism or information source, which the first gauntlet "
                           "gate refuses by design")
        if str(lead.get("horizon") or "") and lead["horizon"] not in mod.HORIZON_CHART:
            missing.append(f"horizon {lead['horizon']!r} maps to no chart")
        return _outcome("map_elites", "GAP",
                        "the niche cannot be built: " + ("; ".join(missing) or "unproposable "
                                                         "session/chart combination"),
                        detail={"niche": key})
    return _outcome("map_elites", "PRODUCED",
                    "one intake row in axis_registry's exact shape; qd_frontier has no seed "
                    "inbox, so it reaches the map through the docket like any other candidate",
                    produced=1, instruments=list(row.get("symbols") or []), direction=None,
                    detail={"niche": key, "axis_cell": row.get("axis_cell"),
                            "timeframe": row.get("timeframe"), "session": row.get("session")})


def p_populations(lead: dict[str, Any], *, budget_s: float,
                  draws: int = DRAWS_PER_POPULATION) -> list[dict[str, Any]]:
    """GFlowNet, GP, symbolic regression and Bayesian search -- one call, four verdicts.

    ONE `search_populations.run` PER LEAD, not four, because the dedupe is ACROSS populations by
    structural hash: two populations converging on one tree have found ONE hypothesis, and
    charging it twice would inflate the multiplicity the gauntlet later deflates by. The credit
    goes to whichever got there first, which is exactly the signal that says two populations are
    doing one job.
    """
    mod, why = _load("populations")
    if mod is None:
        return [_outcome(p, "UNAVAILABLE", why) for p in POPULATIONS]
    syms = list(lead.get("symbols") or [])
    seed = abs(hash(lead["lead_id"])) % (2**31)
    try:
        note = (f"drawn for paradigm_router lead {lead['lead_id']} ({lead['mechanism']})")
        ctx = mod.SearchContext(rng=np.random.default_rng(seed), symbol=(syms[0] if syms else ""),
                                notes=dict.fromkeys(POPULATIONS, note))
        res = mod.run(ctx, n_per_population=int(draws), budget_s=float(budget_s),
                      names=list(POPULATIONS))
    except Exception as exc:
        return [_outcome(p, "NONE", f"{type(exc).__name__}: {exc}") for p in POPULATIONS]
    by_pop: dict[str, int] = {}
    for _expr, name in getattr(res, "proposals", []):
        by_pop[str(name)] = by_pop.get(str(name), 0) + 1
    out: list[dict[str, Any]] = []
    for p in POPULATIONS:
        y = (getattr(res, "yields", {}) or {}).get(p)
        n = int(by_pop.get(p, 0))
        note = str(getattr(y, "note", "") or "") if y is not None else "the population did not run"
        out.append(_outcome(p, "PRODUCED" if n else "NONE",
                            f"{n} well-formed tree(s) over the lead's terminals; {note}",
                            produced=n, instruments=syms, direction=None,
                            detail={"proposed": int(getattr(y, "proposed", 0) or 0),
                                    "unique": int(getattr(y, "unique", 0) or 0)} if y else None))
    return out


def p_program_evolution(lead: dict[str, Any]) -> dict[str, Any]:
    """Program evolution: can the lead's mechanism be SAID in the program IR at all?

    THE LANE EXPOSES NO SEED INTAKE, and the shape of the gap is worth stating exactly, because
    it looks like an intake and is not: `run()` seeds from `templates(symbol)` and then from the
    top `SEED_FROM_DB` rows of `program_db.jsonl` ordered by `Program.best()`. A row written here
    has no evaluations, so `best()` is `-inf`, so it sorts LAST and is never drawn. Writing one
    would produce a database entry nothing reads -- the exact failure the discovery compiler was
    built to end. So the router asks the only question it honestly can: does the lane's template
    library already hold a program that expresses this mechanism? A match is a real result (the
    mechanism is expressible and the lane will draw it unprompted); a miss names the gap.
    """
    mod, why = _load("program_evolution")
    if mod is None:
        return _outcome("program_evolution", "UNAVAILABLE", why)
    syms = list(lead.get("symbols") or [])
    try:
        library = mod.templates(syms[0] if syms else "EURUSD")
    except Exception as exc:
        return _outcome("program_evolution", "NONE", f"{type(exc).__name__}: {exc}")
    text = f"{lead['mechanism']} {lead.get('family') or ''}".lower().replace("-", "_")
    hits = [name for name in library
            if any(tok and tok in text for tok in str(name).split("_"))]
    if not hits:
        return _outcome("program_evolution", "GAP",
                        f"no template of the lane's {len(library)}-program library expresses "
                        f"{lead['mechanism']!r}, and the lane has no seed inbox: run() seeds from "
                        f"templates() and the best-scoring program_db rows, and a fresh row "
                        f"scores -inf and is never drawn",
                        detail={"library": sorted(library)})
    return _outcome("program_evolution", "PRODUCED",
                    f"the mechanism is expressible in the program IR as {', '.join(hits)}; the "
                    f"lane draws these unprompted every pass, so the lead is already covered",
                    produced=len(hits), instruments=syms, direction=None,
                    detail={"templates": hits})


def p_causal_discovery(lead: dict[str, Any], *, artifact: Path | None = None) -> dict[str, Any]:
    """Causal discovery: does the lab's own artifact already hold an edge on this lead?

    A LEAD CANNOT BE FED IN -- `causal_lab.build()` recomputes a PIT-aligned daily panel from
    bars and tests every pair itself; there is no seed. What a lead CAN do is be CHECKED, and
    that check is the valuable half anyway: an independently tested edge on the lead's instrument
    is the one piece of evidence on this desk that was not produced by the search that proposed
    the lead.

    THE EDGE IS RECORDED UNSIGNED. Its coefficient carries a CAUSAL sign, not a trade direction,
    and mapping one to the other here would manufacture agreements and disagreements the evidence
    does not carry.
    """
    src = artifact or CAUSAL_LAB
    try:
        doc = json.loads(src.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return _outcome("causal_discovery", "UNAVAILABLE",
                        f"{src.name} unreadable: {type(exc).__name__}: {exc}")
    syms = set(lead.get("symbols") or [])
    if not syms:
        return _outcome("causal_discovery", "GAP",
                        "the lead declares no instrument, so no node of the panel can be matched")
    edges = [e for e in (doc.get("edges") or []) if isinstance(e, dict)]
    dag = [e for e in ((doc.get("dag") or {}).get("edges") or []) if isinstance(e, dict)]
    hit: list[dict[str, Any]] = []
    for e in edges + dag:
        nodes = {str(e.get("from") or "").upper(), str(e.get("to") or "").upper()}
        touched = {s for s in syms if any(s in n for n in nodes)}
        if touched:
            hit.append({"from": e.get("from"), "to": e.get("to"), "lag": e.get("lag"),
                        "klass": e.get("klass") or "DAG_WEIGHT", "instruments": sorted(touched)})
    if not hit:
        return _outcome("causal_discovery", "NONE",
                        f"the lab's {len(edges)} tested edge(s) and {len(dag)} DAG edge(s) touch "
                        f"none of {sorted(syms)}; an untested pair is not a refuted one",
                        detail={"n_edges": len(edges), "n_dag": len(dag)})
    touched = sorted({s for h in hit for s in h["instruments"]})
    best = sorted(hit, key=lambda h: str(h["klass"]))[0]
    return _outcome("causal_discovery", "PRODUCED",
                    f"{len(hit)} admitted edge(s) on {', '.join(touched)}; strongest class "
                    f"{best['klass']}. Recorded UNSIGNED: an edge carries a causal sign, not a "
                    f"trade direction", produced=len(hit), instruments=touched, direction=None,
                    detail={"edges": hit[:6]})


# --------------------------------------------------------------------------- agreement
def agreement(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Who agreed with whom, over the paradigms that actually produced something.

    THE INSTRUMENT POOL IS A PLURALITY, NOT A UNION, and that distinction is the whole test. A
    union can never disagree with itself: every paradigm's instruments are inside the union by
    construction, so a union pool would report unanimous agreement on every lead forever -- a
    metric that cannot take the value it exists to detect. So each producing paradigm casts ONE
    VOTE PER INSTRUMENT it named, and the pool is the instruments holding the most votes.

    A PARADIGM AGREES when (a) its direction is the plurality direction or unsigned -- an
    unsigned result cannot disagree about a sign it never claimed -- AND (b) it named at least
    one instrument in that pool, or named none at all: a paradigm that produced a mechanism-level
    result without an instrument is not disagreeing about instruments. Everything else that
    produced is a DISAGREEMENT, and a disagreement is a finding: two methods looked at one lead
    and landed somewhere different, which names an assumption one of them is making.

    A paradigm that produced NOTHING is in neither list. Silence is not a vote (L1.28a) -- it is
    reported as its own status and counted in the paradigm's `produced` column.
    """
    spoke = [o for o in outcomes if int(o.get("produced") or 0) > 0]
    if len(spoke) < 2:
        return {"agree": [o["paradigm"] for o in spoke], "disagree": [], "direction": None,
                "instruments": sorted({s for o in spoke for s in o["instruments"]}),
                "why": ("fewer than two paradigms produced anything on this lead: there is "
                        "nothing to agree or disagree about")}
    dirs = [str(o["direction"]) for o in spoke if o.get("direction")]
    plurality = max(sorted(set(dirs)), key=dirs.count) if dirs else None
    names = sorted({s for o in spoke for s in o["instruments"]})
    counts = np.array([sum(1 for o in spoke if s in o["instruments"]) for s in names], dtype=int)
    top = int(counts.max()) if counts.size else 0
    pool = [names[i] for i in np.flatnonzero(counts == top)] if top else []
    agree, disagree = [], []
    for o in spoke:
        d = o.get("direction")
        same_dir = (d is None) or (plurality is None) or (d == plurality)
        inst = set(o["instruments"])
        same_inst = (not inst) or (not pool) or bool(inst & set(pool))
        (agree if (same_dir and same_inst) else disagree).append(o["paradigm"])
    return {"agree": agree, "disagree": disagree, "direction": plurality, "instruments": pool,
            "why": (f"{len(spoke)} paradigm(s) produced; plurality direction "
                    f"{plurality or 'unsigned'}; plurality instruments "
                    f"{', '.join(pool) or 'none named'} at {top} vote(s) each")}


def remember_disagreement(lead: dict[str, Any], verdict: dict[str, Any],
                          outcomes: list[dict[str, Any]]) -> str | None:
    """Method disagreement into `research_memory`, keyed by the lead, as VALUE not as noise."""
    try:
        from libs.moat import registry as reg
    except Exception:
        return None
    payload = {"lead_id": lead["lead_id"], "kind": lead["kind"], "state": lead["state"],
               "mechanism": lead["mechanism"], "family": lead.get("family"),
               "symbols": lead.get("symbols"), "agree": verdict["agree"],
               "disagree": verdict["disagree"], "direction": verdict["direction"],
               "instruments": verdict["instruments"],
               "by_paradigm": {o["paradigm"]: {"status": o["status"], "produced": o["produced"],
                                               "instruments": o["instruments"],
                                               "why": o["why"][:200]} for o in outcomes}}
    with contextlib.suppress(Exception):
        return reg.remember(
            "paradigm_router",
            f"{', '.join(verdict['disagree'])} disagreed with "
            f"{', '.join(verdict['agree']) or 'the plurality'} on lead {lead['lead_id']} "
            f"({lead['mechanism']}): {verdict['why']}",
            kind="method_disagreement", memory_key=f"paradigm:{lead['discovery_id']}",
            payload=payload, evidence={"at": now(), "rule": RULE})
    return None


# --------------------------------------------------------------------------- the pass
def _blank(name: str) -> dict[str, Any]:
    return {"available": None, "fed": 0, "produced": 0, "leads_with_output": 0, "why": ""}


def route(*, max_leads: int = MAX_LEADS, budget_s: float = BUDGET_S,
          dry_run: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Feed every lead to every paradigm inside the budget, and record what each one said."""
    t0 = time.monotonic()
    rows, unmeasured = leads(max_leads)
    tally = {p: _blank(p) for p in PARADIGMS}
    agreements: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []
    intake: list[dict[str, Any]] = []
    fed = 0
    per_lead = max(1.0, float(budget_s) / max(1, len(rows)))
    for lead in rows:
        if time.monotonic() - t0 > float(budget_s):
            unmeasured.append({"what": "leads not routed",
                               "why": f"{len(rows) - fed} lead(s) left unfed when the "
                                      f"{budget_s:.0f}s budget ran out; they are the next pass's "
                                      f"first rows, not a verdict about them"})
            break
        fed += 1
        llm, row = p_llm_seats(lead)
        if row is not None:
            intake.append(row)
        outcomes = [llm, p_mcts(lead), p_map_elites(lead),
                    *p_populations(lead, budget_s=max(1.0, per_lead * 0.5)),
                    p_program_evolution(lead), p_causal_discovery(lead)]
        for o in outcomes:
            slot = tally[o["paradigm"]]
            slot["fed"] += 1
            slot["produced"] += int(o["produced"])
            slot["leads_with_output"] += int(bool(o["produced"]))
            slot["available"] = (o["status"] != "UNAVAILABLE") if slot["available"] is None \
                else bool(slot["available"] and o["status"] != "UNAVAILABLE")
            if not slot["why"] or o["status"] in ("UNAVAILABLE", "GAP"):
                slot["why"] = o["why"]
            if o["status"] in ("UNAVAILABLE", "GAP"):
                gaps.append({"paradigm": o["paradigm"], "lead_id": lead["lead_id"],
                             "status": o["status"], "why": o["why"]})
        verdict = agreement(outcomes)
        agreements.append({"discovery_id": lead["discovery_id"], "lead_id": lead["lead_id"],
                           "mechanism": lead["mechanism"], "agree": verdict["agree"],
                           "disagree": verdict["disagree"], "direction": verdict["direction"],
                           "instruments": verdict["instruments"], "why": verdict["why"],
                           "by_paradigm": {o["paradigm"]: o["status"] for o in outcomes}})
        if verdict["disagree"] and not dry_run:
            remember_disagreement(lead, verdict, outcomes)
    donation = None
    if intake and not dry_run:
        donation = write_intake(intake)
    report = {
        "at": now(), "n_leads": fed, "n_leads_found": len(rows),
        "paradigms": {p: {"available": bool(tally[p]["available"]), "fed": tally[p]["fed"],
                          "produced": tally[p]["produced"],
                          "leads_with_output": tally[p]["leads_with_output"],
                          "why": tally[p]["why"]} for p in PARADIGMS},
        "agreement": agreements,
        "n_disagreements": sum(1 for a in agreements if a["disagree"]),
        "gaps": _fold_gaps(gaps),
        "llm_intake": str(donation) if donation else None,
        "n_intake_rows": len(intake),
        "unmeasured": unmeasured,
        "seconds": round(time.monotonic() - t0, 2),
        "budget_s": float(budget_s),
        "rule": RULE,
    }
    return report, intake


def _fold_gaps(gaps: list[dict[str, str]]) -> list[dict[str, Any]]:
    """One row per (paradigm, status, why), with how many leads hit it. A gap repeated fifty
    times is one gap with a count, not fifty findings."""
    folded: dict[tuple[str, str, str], dict[str, Any]] = {}
    for g in gaps:
        key = (g["paradigm"], g["status"], g["why"][:160])
        row = folded.setdefault(key, {"paradigm": g["paradigm"], "status": g["status"],
                                      "why": g["why"], "n_leads": 0, "example": g["lead_id"]})
        row["n_leads"] += 1
    return sorted(folded.values(), key=lambda r: (-int(r["n_leads"]), str(r["paradigm"])))


def write_intake(rows: list[dict[str, Any]], *, directory: Path | None = None) -> Path:
    """The LLM seats' inbox: one stamped file both compilers already glob."""
    dst = (directory or INTAKE) / f"leads_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.json"
    _write(dst, rows)
    return dst


def _write(path: Path, doc: Any) -> None:
    """Atomic, and it survives the read-only destination that broke the frontier fix on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        os.chmod(path, 0o644)
        os.replace(tmp, path)


def summary(report: dict[str, Any]) -> list[str]:
    """What was routed, which paradigms could speak, and where the methods disagreed."""
    p = report["paradigms"]
    share = [f"{k}={p[k]['leads_with_output']}/{p[k]['fed']}" for k in PARADIGMS]
    lines = [f"PARADIGM ROUTER {report['at']}  leads={report['n_leads']}/"
             f"{report['n_leads_found']}  disagreements={report['n_disagreements']}  "
             f"intake={report['n_intake_rows']} rows  {report['seconds']}s",
             "  leads with output  " + "  ".join(share[:5]),
             "                     " + "  ".join(share[5:])]
    for a in report["agreement"][:6]:
        lines.append(f"  {a['discovery_id'][:28]:<28} agree={','.join(a['agree']) or 'none':<40} "
                     f"disagree={','.join(a['disagree']) or 'none'}")
    for g in report["gaps"][:5]:
        lines.append(f"  GAP {g['paradigm']:<20} x{g['n_leads']:<4} {str(g['why'])[:84]}")
    for u in report["unmeasured"][:3]:
        lines.append(f"  UNMEASURED {u['what']}: {str(u['why'])[:84]}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no report, no intake row, remember nothing")
    ap.add_argument("--max-leads", type=int, default=MAX_LEADS)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    a = ap.parse_args(argv)
    report, _rows = route(max_leads=max(0, int(a.max_leads)), budget_s=float(a.budget_s),
                          dry_run=bool(a.dry_run))
    for line in summary(report):
        print(line, flush=True)
    if a.dry_run:
        print("  --dry-run: nothing written, nothing remembered", flush=True)
        return 0
    _write(OUT, report)
    print(f"-> {OUT}", flush=True)
    # A PASS THAT ROUTED NOTHING IS A VERDICT, NOT A CRASH: exit 2 says the registry held no
    # interpreted lead and no queued candidate, which is a fact about the miners, not this organ.
    return 0 if report["n_leads"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
