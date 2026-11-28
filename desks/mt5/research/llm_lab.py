"""THE OWNED 24/7 MULTI-LAB LLM RESEARCH CIVILIZATION -- reckless questions, ruthless judging.

    py -3 desks/mt5/research/llm_lab.py --once --budget-s 600     # one pass (the hourly leg)
    py -3 desks/mt5/research/llm_lab.py --dry-run                 # plan the pass, call nothing

THE PRINCIPAL'S ORDERS (2026-10-11 / 2026-10-12, standing): a permanent, desk-OWNED laboratory of
independent research labs that continuously invents genuinely novel, economically coherent,
EXECUTABLE strategy hypotheses for the canonical gauntlet -- free-first, never banal, never a
duplicate, never a raw row left sitting untestable, and never with any authority of its own.

WHAT THE DESK OWNS HERE, AND WHAT IS ONLY RENTED. Owned: the lab mandates, the prompts (through
`proposer_seat.build_prompt`, the one hygiene-scanned composer), the coverage map, the ontology,
the novelty classes, the banal filter, the genealogy, the exact-rule compiler, the conversion
debt, the model registry and every artifact. Rented: completions, from `libs.ops.free_chain`
(free cloud providers, then a LOCAL model) and the existing free panel / seat behind
`proposer_seat._ask`. Any provider can vanish and the lab keeps running on the next rung.

THE FUNDAMENTAL LAW, AS CODE.

    GENERATION   sixteen labs (A-P), each with its own scientific mandate, each asked about one
                 coordinate of the research tensor per pass WITHOUT seeing any other lab's current
                 answers (the independent first pass). Then a synthesis call composes across labs
                 and the red team (Lab P) attacks what came back. No lab ever sees a score.
    VALIDATION   none here. An accepted mechanism becomes an ordinary `kind: hypothesis` row with
                 an exact registered-family recipe under `data/intelligence/llm_lab/`, which the
                 miner candidate compiler reads like every other seat's donation, and the same ten
                 gates judge it. Models have ZERO promotion authority: `proposer_seat` strips any
                 verdict a model volunteers and charges every accepted proposal its trials.

EVERY PROPOSAL ENDS IN EXACTLY ONE OF THESE, NEVER SILENTLY:

    EMITTED              an exact cell of a registered family (or a valid `formula` expression),
                         novelty class MECHANISM_NEIGHBOUR / COMPOSITIONAL_DESCENDANT /
                         GENUINELY_NOVEL, donated for the gauntlet
    EXACT_DUPLICATE      collapsed onto the twin it names (no trial spent)
    PARAMETER_NEIGHBOUR  recorded under its parent's genealogy (a sweep step, not a new bet)
    BANAL_BASELINE       a generic indicator recipe; kept as a baseline, never credited as research
    CONVERSION DEBT      NEEDS_DATA / NEEDS_EXACT_RULE_EXTRACTION / NEEDS_PIT_SOURCE /
                         NEEDS_EXECUTABLE_FAMILY / NEEDS_PARAMETER_INFERENCE /
                         NEEDS_INSTRUMENT_MAPPING -- persisted, re-compiled every pass (temporal
                         reopening: a new family, series or symbol resolves it), and the
                         rule-shaped debts are re-asked to a converter call. NEEDS_DATA writes a
                         named data request for the miners. Nothing is invented to close a gap.
    REFUSED              a banned family, or a symbol the lane policy forbids for that family

COVERAGE CONSERVATION. The coordinate space is lab x mechanism class x asset class x horizon, and
the mechanism ontology is NEVER closed: any class a lab names that the ontology lacks is added and
becomes owed work for every lab. A per-pass cap means NOT THIS PASS -- owed coordinates are kept,
counted and visited in stable cursor order, with a permanent cold-exploration share drawn at
random so no region ever has zero probability, and a yield share that returns to coordinates
whose descendants survived.

MODELS COMPETE FOR WORK. Every free model the chain can list is registered (local models only
after a license review against an allowlist); each lab's model is drawn by Thompson sampling on
that model's measured rate of novel exact cells, so new models are tried and productive ones earn
more of the hour. A model's record is a measurement of usefulness, never of truth.

BUDGET. Paid spend is OFF: this process forces QUANT_FREE_TIER=1 unless the principal sets
QUANT_LLM_LAB_PAID=1, and then `llm_seat`'s own monthly cap still binds. Calls per pass and per
day are capped (QUANT_LLM_LAB_MAX_CALLS, QUANT_LLM_LAB_DAILY_CALLS); a capped pass is owed work.

JEV (Lab L). The semantic lab writes typed questions into a persistent job queue and compiles each
into an `exogenous_conditioner` cell on the question's own series. Until a Jev feature series
exists in the lake the cell is NEEDS_DATA debt, and the Jev provider reads UNMEASURED: no
TypeSafe adapter is wired because no key is acquired and its current API was not verified, and
this module will not guess an API's fields.

CENTRAL-BANK TONE (role CB_TONE, `cb_tone_lab.py`). PBoC, BoJ, SARB, RBA and CBRT statements read
in their original language, scored by a native lexicon and by a free-tier model, written as PIT
lake series `cb_tone_<bank>` and donated as conditioner cells; contaminated model readings are
kept out of the donated columns by the look-ahead guard.

    desks/mt5/reports/LLM_LAB.json                     the pass, the coverage, the models, the debt
    desks/mt5/data/intelligence/llm_lab/discoveries_*  the donations the compiler reads
    desks/mt5/data/llm_lab/*                           the lab's own state (outside intelligence/)
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if "libs" in sys.modules and not getattr(sys.modules["libs"], "__file__", None):
    for _m in [k for k in sys.modules if k == "libs" or k.startswith("libs.")]:
        del sys.modules[_m]


from llm_lab_cells import (  # noqa: E402,F401  (re-exported: callers read them off llm_lab)
    compile_payload,
    donation_row,
    lookahead_guard,
    process,
    retry_debt,
)
from llm_lab_core import (  # noqa: E402,F401  (re-exported: callers read them off llm_lab)
    _BANAL,
    _NOVEL_ELEMENT,
    _SKIP_PARAMS,
    _STOP,
    _WORD,
    ASSET_CLASSES,
    BLOCKERS,
    CALLS,
    COLD_SHARE,
    COVERAGE,
    COVERAGE_STATES,
    DATA_REQUESTS,
    DEBT,
    EMITTED_CLASSES,
    EXOTIC_CAP,
    EXOTIC_CLASSES,
    EXOTIC_KEEP,
    FORMULA_GRAMMAR,
    GAP_CLASSES,
    GAP_NOTE,
    GAP_SHARE,
    GAUNTLET_PROBE,
    GENEALOGY,
    GRAMMAR,
    HORIZONS,
    INVENTORS,
    JEV_JOBS,
    LAB_BY_KEY,
    LABS,
    LANE_POLICY_ERRORS,
    LICENSE_OK,
    LITERATURE_DIRS,
    LITERATURE_FILES_PER_DIR,
    MECH_NEIGHBOUR_J,
    MODELS,
    NOVELTY_CLASSES,
    ONTOLOGY,
    PRIORITY_LABS,
    PROBE_CACHE_NAME,
    PROBE_TIMEOUT_S,
    REFEREE_GRAMMAR,
    REFEREE_MAX,
    REFEREE_TASK,
    REVISION_TASK,
    ROLE_LABS,
    ROTATION,
    RULE,
    STATE_DIR,
    TASK_RULES,
    UNIVERSE,
    UNMEASURED,
    UNMEASURED_TAG,
    WRAPPERS,
    YIELD_SHARE,
    Ask,
    Compiled,
    Coverage,
    FamilySpec,
    Lab,
    Memory,
    Tally,
    _append_jsonl,
    _calls_left,
    _cb_tone_role,
    _choose_coordinate,
    _coerce,
    _collector_role,
    _count_calls,
    _expr_ok,
    _h,
    _jsonl,
    _lane_ok,
    _local_license,
    _now,
    _ontology,
    _param_twin,
    _probe_gauntlet,
    _read_json,
    _rel,
    _resolve_symbols,
    _save_ontology,
    _series_present,
    _symbols_for,
    _validate,
    _validate_attack,
    _validate_referee,
    _write_json,
    all_family_names,
    assign_model,
    banal,
    breadth_gap,
    cell_identity,
    choose_coordinate,
    classify,
    converter_asks,
    coord_id,
    coordinates,
    enforce_exotic_cap,
    family_registry,
    hunt_models,
    jaccard,
    jev_series_name,
    market_share,
    menu_lines,
    observe_model,
    openrouter_pass_share,
    owed,
    prioritised,
    referee_model,
    referee_targets,
    registry_fingerprint,
    slug,
    synthesis_lines,
    tokens,
    universe,
)

DONATE_DIR = BASE / "data" / "intelligence" / "llm_lab"
ORGAN = "llm_lab"
REPORT = BASE / "reports" / "LLM_LAB.json"
GAUNTLET = BASE / "scripts" / "external_gauntlet.py"
VERDICTS = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SARES_DIR = BASE / "data" / "intelligence" / "sares"


# ============================================================================ literature
#: The desk's own paper corpora (free arXiv q-fin, academic listings, central-bank and BIS texts),
#: read locally: grounding costs no fetch and no key. A host without them says UNMEASURED.
INTEL = BASE / "data" / "intelligence"
_LIT_CACHE: list[tuple[frozenset[str], str]] = []


def literature_index() -> list[tuple[frozenset[str], str]]:
    """[(tokens, line)] over the newest files of each corpus, built once per process."""
    if _LIT_CACHE:
        return _LIT_CACHE
    seen: set[str] = set()
    for d in LITERATURE_DIRS:
        for f in sorted((INTEL / d).glob("discoveries_*.json"))[-LITERATURE_FILES_PER_DIR:]:
            doc = _read_json(f, [])
            rows = doc if isinstance(doc, list) else (doc or {}).get("discoveries") or []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                title = str(r.get("title") or "").strip()
                url = str(r.get("url") or "").strip()
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())
                body = str(r.get("text") or r.get("summary") or r.get("abstract") or "")
                _LIT_CACHE.append((tokens(f"{title} {body[:800]}"),
                                   f"paper: {title[:140]} <{url[:120]}> {body[:220]}"))
    return _LIT_CACHE


def literature_lines(query: str, k: int = 4) -> list[str]:
    idx = literature_index()
    if not idx:
        return ["literature: UNMEASURED on this host (no paper corpus under data/intelligence)"]
    q = tokens(query)
    scored = sorted(((len(q & t) / (len(q) or 1), i) for i, (t, _) in enumerate(idx)),
                    reverse=True)
    hits = [idx[i][1] for sc, i in scored[:k] if sc > 0]
    return hits or ["literature: no paper in the desk's corpus matches this coordinate"]


def referee_context(g: dict[str, Any]) -> list[str]:
    cell = g.get("cell") or {}
    return [f"hypothesis node {g['node']} (lab {g.get('lab')}): {g.get('mechanism', '')[:300]}",
            f"falsifier: {g.get('falsifier', '')[:200]}",
            f"cell: {cell.get('family')} on {cell.get('symbol')} params "
            f"{json.dumps(cell.get('params'), default=str)[:200]}",
            *literature_lines(f"{g.get('mechanism_class', '')} {g.get('mechanism', '')}", k=3)]


# ============================================================================ feeds
def feed_lines(lab: Lab, extra: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for f in lab.feeds:
        if f == "graveyard":
            import llm_lab_roles as roles
            dead = [r for r in _jsonl(VERDICTS, limit=4000) if r.get("passed") is False
                    and not roles.held_out(str(r.get("terminal_gate") or r.get("gate") or ""),
                                           str(r.get("reason") or r.get("why") or ""))]
            for r in dead[-8:]:
                out.append(f"graveyard: {str(r.get('cell'))[:70]} family={r.get('family')} "
                           f"died at gate {r.get('gate')}")
            if not dead:
                out.append("graveyard: UNMEASURED on this host (no verdict ledger)")
        elif f == "sares":
            files = sorted(SARES_DIR.glob("discoveries_*.json"))[-2:]
            rows: list[dict[str, Any]] = []
            for p in files:
                doc = _read_json(p, {}) or {}
                rows += [r for r in doc.get("discoveries") or [] if isinstance(r, dict)]
            for r in rows[-8:]:
                frag = r.get("mechanism") or r.get("testable_claim") or r.get("title")
                out.append(f"donor fragment: {str(frag)[:150]}")
            if not rows:
                out.append("donor fragments: UNMEASURED on this host (no SARES donations)")
        elif f == "survivors":
            try:
                import novelty_gate as ng
                lib = ng.Library.load()
                fams = Counter(m.family for m in lib.members if m.origin in ("survivor", "sleeve"))
                out.append("book holds: " + ", ".join(f"{f}x{n}" for f, n in fams.most_common(12))
                           if fams else "book: UNMEASURED on this host")
            except Exception:                          # pragma: no cover
                out.append("book: UNMEASURED")
        else:
            out.extend(extra.get(f, [])[:8])
    return out


def build_ask(lab: Lab, coord: dict[str, str], why: str, model: str, reg: dict[str, FamilySpec],
              uni: dict[str, str], rng: random.Random, own_recent: Sequence[str],
              extra: dict[str, list[str]]) -> Ask:
    ctx = [f"lab {lab.key} ({lab.name}): {lab.mandate[:220]}",
           f"coordinate: mechanism_class={coord['mechanism_class']} asset_class="
           f"{coord['asset_class']} horizon={coord['horizon']}",
           "symbols in that class: " + ", ".join(_symbols_for(coord["asset_class"], uni, rng)),
           GAP_NOTE,
           "all registered families: " + all_family_names(reg)[:900],
           FORMULA_GRAMMAR]
    ctx += [f"menu: {ln}" for ln in menu_lines(reg, lab, rng)]
    ctx += literature_lines(f"{coord['mechanism_class'].replace('_', ' ')} "
                            f"{coord['asset_class']} {coord['horizon']} {lab.mandate[:120]}")
    ctx += feed_lines(lab, extra)
    ctx += [f"gauntlet {ln}" for ln in (extra.get(f"verdicts:{lab.key}") or [])[:6]]
    ctx += [f"already proposed by this lab here (do NOT repeat): {m[:120]}" for m in own_recent[:5]]
    task = (f"{lab.mandate} Propose genuinely new mechanisms for the coordinate given. "
            f"{TASK_RULES}")
    return Ask(lab, coord, why, model, ctx[:40], task)


def _seat() -> Any:
    """The proposer seat, or None. Guarded: a box without it plans the pass and calls nothing."""
    try:
        from libs.research import proposer_seat
    except Exception:                                  # pragma: no cover - defensive
        return None
    return proposer_seat


def _call(ask: Ask, n: int, timeout: float) -> list[Any]:
    ps = _seat()
    if ps is None:
        return []
    return ps._asked(ORGAN, role="generation", task=ask.task, grammar=GRAMMAR,
                     context=ask.context, n=n, label="candidate", validate=_validate,
                     timeout=timeout, model_hint=ask.model)


#: KNOWN TRAINING CUTOFFS, by model-id fragment -> "YYYY-MM-DD". Empty by default ON PURPOSE: a
#: cutoff written from memory is a claim, and a wrong one that is too EARLY would let in-sample
#: history count as evidence. `desks/mt5/data/llm_lab/model_cutoffs.json` ({"<fragment>":
#: "<date>", ...}, each with the provider's own documentation as its source) may name one.
MODEL_CUTOFFS = STATE_DIR / "model_cutoffs.json"


def coverage_from_outcomes(cov: Coverage) -> dict[str, int]:
    """Lift coordinates whose emitted cells the gauntlet has since judged or certified."""
    judged: dict[str, bool] = {}
    for r in _jsonl(VERDICTS, limit=200000):
        c = str(r.get("cell") or "")
        if c:
            judged[c] = judged.get(c, True) and bool(r.get("passed"))
    certified: set[str] = set()
    forward: set[str] = set()
    try:
        import novelty_gate as ng
        lib = ng.Library.load()
        for m in lib.members:
            if m.origin == "sleeve" and m.ident:
                forward.add(m.ident)
            elif m.origin == "survivor" and m.ident:
                certified.add(m.ident)
    except Exception:                                  # pragma: no cover
        pass
    for row in cov.doc["coords"].values():
        cells = row.get("cells") or []
        state = None
        if any(c in forward for c in cells):
            state = "FORWARD"
        elif any(c in certified for c in cells):
            state = "CERTIFIED"
        elif cells and all(c in judged and not judged[c] for c in cells):
            state = "GRAVEYARDED"
        elif any(c in judged for c in cells):
            state = "TESTED"
        if state:
            row["state"] = state
    return dict(Counter(str(r.get("state")) for r in cov.doc["coords"].values()))


def gauntlet_status() -> dict[str, Any]:
    """Whether the canonical gauntlet trims LLM-born cells, judged by behaviour, cached per
    gauntlet file hash (the probe imports the gauntlet, so it runs once per version of it).

    No substring precheck (audit SF2 on 37bb136b4): a gauntlet that RE-EXPORTS llm_born and
    evidence_trim from a helper module meets the contract without ever spelling "def llm_born(",
    so only the probe decides. Only a definite verdict is cached."""
    try:
        raw = GAUNTLET.read_bytes()
    except OSError as exc:
        return {"trims": False, "why": f"gauntlet unreadable: {type(exc).__name__}"}
    sha = hashlib.sha256(raw).hexdigest()
    cache = _read_json(STATE_DIR / PROBE_CACHE_NAME, {}) or {}
    hit = cache.get(sha) if isinstance(cache, dict) else None
    if not (isinstance(hit, dict) and isinstance(hit.get("trims"), bool)):
        ok, why = _probe_gauntlet(GAUNTLET)
        if ok is None:
            return {"trims": False, "measured": False, "why": why, "gauntlet_sha256": sha}
        hit = {"trims": ok, "why": why, "probed_at": _now()}
        with contextlib.suppress(OSError):
            _write_json(STATE_DIR / PROBE_CACHE_NAME, {sha: hit})
    return {"trims": bool(hit["trims"]), "why": str(hit.get("why")), "gauntlet_sha256": sha}


def gauntlet_trims() -> bool:
    """True only when the canonical gauntlet MEETS the trim contract above (the sealed patch
    `llm_lookahead_gauntlet`), never when it merely names the functions. Until then the lab's
    cells would reach every gate untrimmed, so they are HELD, never donated (audit blocker on
    #332, 2026-10-13). The first pass after a conforming patch lands releases them."""
    return bool(gauntlet_status()["trims"])


def donation_target(default: Path) -> Path:
    """Where an LLM-lab donation may be written: the compiler's seat dir, or the held queue."""
    return default if gauntlet_trims() else STATE_DIR / "held_donations" / default.name


def release_held(dest: Path | None = None) -> dict[str, Any]:
    """Move held donations into the seat dir once the gauntlet trims. Nothing is lost while held."""
    held = STATE_DIR / "held_donations"
    # One held subdirectory per destination seat, so a release keeps each donor's attribution.
    files = sorted(held.glob("*/*.json")) if held.is_dir() else []
    status = gauntlet_status()
    if not status["trims"]:
        # HELD BECAUSE THE PATCH IS ABSENT IS AN UNWIRED ORGAN, NOT A QUIET STATE (III.16): every
        # cell this lab mints is inert until the gauntlet trims, so the pass says so in RED.
        return {"state": "HELD", "files": len(files), "why": status["why"], "red": True,
                "defect": "UNWIRED (III.16): the lab's cells cannot reach the gauntlet until "
                          "the sealed patch llm_lookahead_gauntlet lands and meets the trim "
                          "contract (llm_lab.GAUNTLET_PROBE)"}
    root = (dest or DONATE_DIR).parent
    moved = 0
    for f in files:
        seat = root / f.parent.name
        seat.mkdir(parents=True, exist_ok=True)
        os.replace(f, seat / f.name)
        moved += 1
    return {"state": "DONATING", "released": moved}


def run(*, budget_s: float = 600.0, max_calls: int | None = None, dry_run: bool = False,
        seed: int | None = None, workers: int = 4) -> dict[str, Any]:
    started = time.time()
    LANE_POLICY_ERRORS.clear()
    if os.environ.get("QUANT_LLM_LAB_PAID", "0") != "1":
        os.environ["QUANT_FREE_TIER"] = "1"
    donations = release_held() if not dry_run else {"state": "dry run"}
    max_calls = int(max_calls if max_calls is not None else
                    os.environ.get("QUANT_LLM_LAB_MAX_CALLS", "24"))
    # The provider's own quota (a 429 cools the rung) is the binding daily limit; this cap only
    # stops a runaway loop, so it sits far above an hourly pass that covers every model.
    daily_cap = int(os.environ.get("QUANT_LLM_LAB_DAILY_CALLS", "3000"))
    # Refresh OpenRouter's own account limits once a pass (cached an hour): every budget that
    # reads them moves from 50 to 1,000 a day when credit lands, and the report shows whether a
    # paid id could ever leave this box (it cannot unless QUANT_LLM_LAB_PAID=1).
    from libs.ops import openrouter_guard
    or_key = {} if dry_run else openrouter_guard.key_info()
    rng = random.Random(seed if seed is not None else int(started))  # noqa: S311 - not crypto
    reg = family_registry()
    uni = universe()
    fp = registry_fingerprint(reg)
    ontology = _ontology()
    cov = Coverage.load()
    models: dict[str, Any] = _read_json(MODELS, {}) or {}
    mem = Memory.load()
    ps = _seat()
    try:
        seat_on = bool(ps is not None and ps.enabled())
    except Exception:                                  # pragma: no cover
        seat_on = False
    try:
        from libs.ops import free_chain
        chain_status = free_chain.status()
    except Exception:                                  # pragma: no cover
        chain_status = {"verdict": UNMEASURED}

    tallies: dict[str, Tally] = {lab.key: Tally() for lab in LABS}
    tallies["SYNTHESIS"] = Tally()
    tallies["CONVERTER"] = Tally()
    tallies["REFEREE"] = Tally()
    tallies["REVISION"] = Tally()
    outputs: dict[str, list[dict[str, Any]]] = {k: [] for k in (
        "genealogy", "donate", "debt", "data_requests", "jev", "classes", "attacks",
        "referee")}
    plan: list[dict[str, Any]] = []
    calls_budget = min(max_calls, _calls_left(daily_cap))
    hunted: list[str] = []
    if seat_on and not dry_run:
        hunted = hunt_models(models, budget_s=min(30.0, budget_s / 10))
    # EVERY MODEL, EVERY CYCLE: the pass is sized to give each registered model one call on top of
    # the labs' own, inside the daily cap. A model the cap still leaves out is named in the
    # coverage report, never silently skipped.
    n_registered = sum(1 for r in models.values() if r.get("status") == "REGISTERED")
    calls_budget = min(max(max_calls, n_registered + len(INVENTORS) + 6), _calls_left(daily_cap))
    # ...unless OpenRouter's MEASURED allowance says otherwise: then the pass spends exactly its
    # even share of the day, and models rotate least-recently-asked first inside it.
    share = openrouter_pass_share() if seat_on and not dry_run else {}
    if share:
        calls_budget = min(int(share["per_pass"]), _calls_left(daily_cap))
    rotation: dict[str, str] = _read_json(ROTATION, {}) or {}

    #: (lab, model, wall seconds, ideas returned) per call: the funnel's compute and idea counts.
    usage: list[tuple[str, str, float, int]] = []

    def _go(ask: Ask) -> tuple[Ask, list[Any]]:
        left = budget_s - (time.time() - started)
        if left < 30:
            return ask, []
        t0 = time.time()
        try:
            got = _call(ask, n=4, timeout=min(120.0, left))
        except Exception as exc:          # pragma: no cover - one lab never kills the pass
            got = [("error", str(exc)[:160])]
        ideas = sum(1 for p in got if getattr(p, "payload", None) is not None)
        lab_key = ask.coord.get("lab") if ask.coord.get("lab") in ("SYNTHESIS",) else ask.lab.key
        usage.append((str(lab_key), ask.model, time.time() - t0, ideas))
        return ask, got

    calls_made = 0
    # ---- phase 0: conversion FIRST. Re-compile everything owed; re-ask the rule-shaped debt.
    debt = retry_debt(reg, uni, mem, tallies["CONVERTER"], outputs, fp, write=not dry_run)
    if seat_on and not dry_run and calls_made < calls_budget:
        conv = converter_asks(debt["rule_shaped_open"], reg, uni, rng,
                              k=min(4, calls_budget - calls_made))
        for ask in conv:
            if budget_s - (time.time() - started) < 45:
                break
            _, props = _go(ask)
            calls_made += 1
            t = tallies["CONVERTER"]
            t.asked += 1
            for p in [p for p in props if not isinstance(p, tuple)]:
                process(p, "CONVERTER", ask.coord, reg, uni, mem, t, models, outputs)

    # ---- phase 0b: the CENTRAL-BANK TONE role (idea 18). Native-language statements scored
    # into point-in-time lake series; the lexicon half runs even with the seat dark.
    cb_tone: dict[str, Any] = {"state": "NOT_RUN"} if not dry_run else {"state": "dry run"}
    if not dry_run and budget_s - (time.time() - started) > 90:
        cb_tone = _cb_tone_role(budget_s=min(150.0, budget_s * 0.25),
                                max_llm=max(0, min(8, calls_budget - calls_made)) if seat_on
                                else 0)
        calls_made += int((cb_tone.get("model") or {}).get("calls") or 0)

    # ---- phase 0c: the COLLECTOR role. Breadth-feed sources become declarative specs a fixed
    # fetcher runs (no model-written code); working specs refresh every pass with no call.
    collector: dict[str, Any] = {"state": "NOT_RUN"} if not dry_run else {"state": "dry run"}
    if not dry_run and budget_s - (time.time() - started) > 90:
        collector = _collector_role(budget_s=min(120.0, budget_s * 0.2),
                                    max_llm=max(0, min(4, calls_budget - calls_made)) if seat_on
                                    else 0)
        calls_made += int(collector.get("asked") or 0)

    # ---- phase 1: the independent first pass. No lab sees another lab's current answers.
    own_recent: dict[tuple[str, str], list[str]] = {}
    for g in _jsonl(GENEALOGY, limit=5000):
        c = g.get("coordinate") or {}
        own_recent.setdefault((str(g.get("lab")), str(c.get("mechanism_class"))), []).append(
            str(g.get("mechanism") or ""))
    used_models: set[str] = set()
    asks: list[Ask] = []
    extra: dict[str, list[str]] = {"disagreement": list((_read_json(REPORT, {}) or {})
                                                        .get("disagreements") or [])[:8],
                                   "jev": ["Jev answers are typed: probability in [0,1], a "
                                           "score in [-1,1] or a choice; the answer series is "
                                           "point-in-time by publication stamp"]}
    import llm_lab_roles as roles
    credit: dict[str, Any] = _read_json(STATE_DIR / "verdict_credit.json", {}) or {}
    for key, lines in (credit.get("feedback") or {}).items():
        extra[f"verdicts:{key}"] = list(lines)
    order = prioritised(rng, credit)
    # Under a measured share the labs draw models from the rotation queue (least recently asked
    # first), so a capped pass never spends its few calls on models the last pass already asked;
    # with room to spare the verdict loop's yield ranking picks.
    queue = sorted((k for k, r in models.items() if r.get("status") == "REGISTERED"),
                   key=lambda k: (str(rotation.get(k) or ""), k)) if share else []
    for lab in order:
        coord, why = choose_coordinate(lab, ontology, cov, rng)
        coord, why = enforce_exotic_cap(coord, why, [a.coord for a in asks], rng)
        model = (next((k for k in queue if k not in used_models), None) if share
                 else assign_model(models, rng, used_models, credit))
        if model:
            used_models.add(model)
        recent = own_recent.get((lab.key, coord["mechanism_class"]), [])[-5:]
        ask = build_ask(lab, coord, why, model, reg, uni, rng, recent, extra)
        if len(asks) < calls_budget - calls_made:
            asks.append(ask)
            plan.append({"lab": lab.key, "coordinate": coord, "why": why, "model": model or
                         "default_route"})
        else:
            cov.touch(coord_id(coord), coord, "QUEUED")
            plan.append({"lab": lab.key, "coordinate": coord, "why": why, "state": "QUEUED",
                         "reason": "per-pass call cap: NOT THIS PASS, owed"})

    # MODEL COVERAGE: every registered model the labs' draws left out gets its own ask, labs in
    # rotation, so each free model produces on every cycle and earns (or fails to earn) credit.
    registered = [k for k, r in models.items() if r.get("status") == "REGISTERED"]
    # Least recently asked first (never-asked before all), so a capped pass still reaches every
    # model within the rotation window; any share left after one call each goes round again.
    uncovered = sorted((k for k in registered if k not in used_models),
                       key=lambda k: (str(rotation.get(k) or ""), k))
    if share and registered:
        spare = calls_budget - calls_made - len(asks) - len(uncovered)
        again = sorted(registered, key=lambda k: (str(rotation.get(k) or ""), k))
        uncovered += [again[i % len(again)] for i in range(max(0, spare))]
    for i, mkey in enumerate(uncovered):
        lab = order[i % len(order)]
        if len(asks) >= calls_budget - calls_made:
            plan.append({"lab": lab.key, "model": mkey, "state": "QUEUED",
                         "reason": "daily call cap: model coverage owed this cycle"})
            continue
        coord, why = choose_coordinate(lab, ontology, cov, rng)
        coord, why = enforce_exotic_cap(coord, why, [a.coord for a in asks], rng)
        recent = own_recent.get((lab.key, coord["mechanism_class"]), [])[-5:]
        asks.append(build_ask(lab, coord, why, mkey, reg, uni, rng, recent, extra))
        used_models.add(mkey)
        plan.append({"lab": lab.key, "coordinate": coord, "why": "model_coverage",
                     "model": mkey})

    pass_cov: dict[str, dict[str, Any]] = {}
    if seat_on and not dry_run and asks:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            results = list(pool.map(_go, asks))
        for ask, props in results:
            t = tallies[ask.lab.key]
            t.asked += 1
            calls_made += 1
            props = [p for p in props if not isinstance(p, tuple)]
            if any(getattr(p, "payload", None) is not None or p.accepted for p in props):
                t.replies += 1
            answered = [p for p in props if getattr(p, "payload", None) is not None]
            model_key = next((str(p.provenance.model) for p in props
                              if getattr(p.provenance, "model", "")), "")
            if ask.model:
                pc = pass_cov.setdefault(ask.model, {"asked": 0, "answered": 0,
                                                     "fell_through_to": []})
                pc["asked"] += 1
                if model_key == ask.model and answered:
                    pc["answered"] += 1
                elif model_key and model_key not in pc["fell_through_to"]:
                    pc["fell_through_to"].append(model_key)
            if model_key:
                observe_model(models, model_key)
            for key in {ask.model, model_key} - {""}:
                m = models.get(key)
                if m is not None:
                    m["asked"] = int(m.get("asked", 0)) + 1
                    m["replies"] = int(m.get("replies", 0)) + int(bool(answered))
            before = len(outputs["genealogy"])
            for p in props:
                process(p, ask.lab.key, ask.coord, reg, uni, mem, t, models, outputs)
            new = outputs["genealogy"][before:]
            disp = Counter(g.get("disposition") for g in new)
            state = ("DISCOVERED" if disp.get("EMITTED") else
                     "PARTIAL" if disp.get("CONVERSION_DEBT") else
                     "DUPLICATE" if disp.get("EXACT_DUPLICATE") or disp.get("PARAMETER_NEIGHBOUR")
                     else "BLOCKED" if disp.get("REFUSED") or disp.get("BANAL_BASELINE")
                     else "INVALID")
            cov.touch(coord_id(ask.coord), ask.coord, state,
                      cells=[g["cell_id"] for g in new if g.get("disposition") == "EMITTED"],
                      novel=sum(1 for g in new if g.get("novelty_class") == "GENUINELY_NOVEL"))
    elif asks and not dry_run:
        for ask in asks:
            cov.touch(coord_id(ask.coord), ask.coord, "QUEUED")

    # ---- phase 1b: the REFEREE LOOP. Referee on another model, then the proposer revises.
    if seat_on and not dry_run and ps is not None:
        for g in referee_targets(outputs, REFEREE_MAX):
            if calls_made + 2 > calls_budget or budget_s - (time.time() - started) < 90:
                break
            ref_model = referee_model(models, str(g.get("model") or ""), rng, credit)
            t0 = time.time()
            got = ps._asked(ORGAN, role="generation", task=REFEREE_TASK, grammar=REFEREE_GRAMMAR,
                            context=referee_context(g), n=1, label="referee",
                            validate=_validate_referee, timeout=120.0, model_hint=ref_model)
            calls_made += 1
            tallies["REFEREE"].asked += 1
            report = next((p.payload for p in got if p.accepted and isinstance(p.payload, dict)),
                          None)
            usage.append(("REFEREE", ref_model, time.time() - t0, int(report is not None)))
            if report is None:
                tallies["REFEREE"].discarded += 1
                continue
            tallies["REFEREE"].accepted += 1
            rep = {"node": g["node"], "referee_model": next(
                       (str(p.provenance.model) for p in got if p.accepted), ref_model),
                   "attacks": [str(a)[:240] for a in report.get("attacks") or []][:5],
                   "snooping_risk": str(report.get("snooping_risk") or "")[:240],
                   "competing_explanations": [str(a)[:240] for a in
                                              report.get("competing_explanations") or []][:4],
                   "separating_test": str(report.get("separating_test") or "")[:200],
                   "verdict": str(report.get("verdict") or "")[:12], "at": _now()}
            outputs["referee"].append(rep)
            for d in outputs["donate"]:
                if d.get("genealogy", {}).get("node") == g["node"]:
                    d["referee"] = rep
            t0 = time.time()
            rev = ps._asked(ORGAN, role="generation", task=REVISION_TASK + TASK_RULES,
                            grammar=GRAMMAR, context=[
                                *referee_context(g),
                                "referee attacks: " + " | ".join(rep["attacks"])[:600],
                                f"snooping risk: {rep['snooping_risk']}",
                                "rival explanations: "
                                + " | ".join(rep["competing_explanations"])[:500],
                                f"referee's separating test: {rep['separating_test']}",
                                "all registered families: " + all_family_names(reg)[:900],
                                FORMULA_GRAMMAR][:40],
                            n=2, label="candidate", validate=_validate, timeout=120.0,
                            model_hint=str(g.get("model") or ""))
            calls_made += 1
            tallies["REVISION"].asked += 1
            revised = [p for p in rev if not isinstance(p, tuple)]
            usage.append(("REVISION", str(g.get("model") or ""), time.time() - t0,
                          sum(1 for p in revised if getattr(p, "payload", None) is not None)))
            for p in revised:
                if isinstance(getattr(p, "payload", None), dict):
                    parents = [str(x) for x in p.payload.get("parents") or []]
                    p.payload["parents"] = [g["node"], *[x for x in parents if x != g["node"]]]
                process(p, "REVISION", g.get("coordinate") or {"mechanism_class": "revision",
                                                              "asset_class": "", "horizon": ""},
                        reg, uni, mem, tallies["REVISION"], models, outputs)

    # ---- phase 2: synthesis across the independent answers, then the red team.
    menu, redisc, disagree = synthesis_lines(outputs)
    if seat_on and not dry_run and menu and calls_made < calls_budget \
            and budget_s - (time.time() - started) > 60:
        syn = Ask(LAB_BY_KEY["A"], {"lab": "SYNTHESIS", "mechanism_class": "composition",
                                    "asset_class": "", "horizon": ""}, "synthesis", "",
                  [*menu, "all registered families: " + all_family_names(reg)[:900],
                   FORMULA_GRAMMAR, *[f"menu: {ln}" for ln in
                                      menu_lines(reg, LABS[0], rng, k=10)]][:40],
                  "SYNTHESIS: combine mechanisms from DIFFERENT labs above into compositions whose "
                  "joint condition is economically meaningful. Put the source node ids in parents. "
                  + TASK_RULES)
        _, props = _go(syn)
        calls_made += 1
        t = tallies["SYNTHESIS"]
        t.asked += 1
        for p in [p for p in props if not isinstance(p, tuple)]:
            process(p, "SYNTHESIS", syn.coord, reg, uni, mem, t, models, outputs)
        if calls_made < calls_budget and budget_s - (time.time() - started) > 60:
            red = Ask(LAB_BY_KEY["P"], {"lab": "P", "mechanism_class": "alternative_explanation",
                                        "asset_class": "", "horizon": ""}, "red_team", "",
                      menu[:20],
                      LAB_BY_KEY["P"].mandate + ' Return {"target": "<node id>", "alternative": '
                      '"<the rival explanation>", "falsifier": "<cheapest test that separates '
                      'them>"} per line. You have no authority: attacks are recorded, not obeyed.')
            got = ps._asked(ORGAN, role="generation", task=red.task, grammar=(
                '{"target": "<node id>", "alternative": "<rival explanation, <=240 chars>", '
                '"falsifier": "<cheapest separating test, <=200 chars>"}'),
                context=red.context, n=8, label="attack", validate=_validate_attack,
                timeout=120.0) if ps is not None else []
            calls_made += 1
            tallies["P"].asked += 1
            for p in got:
                if p.accepted and isinstance(p.payload, dict):
                    pl = p.payload
                    outputs["attacks"].append({"target": str(pl.get("target"))[:60],
                                               "alternative": str(pl.get("alternative"))[:300],
                                               "falsifier": str(pl.get("falsifier"))[:200],
                                               "model": p.provenance.model, "at": _now()})
            tallies["P"].accepted += len(outputs["attacks"])

    # ---- phase 3: the roles -- missed moves (Q), code lab (R), source scout (S), sleeve red team
    # (T). Same call budget, same free chain, same zero authority.
    role_report: dict[str, Any] = {"state": "dry run"} if dry_run else {}
    if not dry_run and budget_s - (time.time() - started) > 60:
        try:
            role_report, role_calls = roles.run(
                lab=sys.modules[__name__], reg=reg, uni=uni, mem=mem, tallies=tallies,
                models=models, outputs=outputs, rng=rng,
                calls_left=max(0, calls_budget - calls_made),
                deadline=started + budget_s - 30, seat_on=seat_on)
            calls_made += role_calls
        except Exception as exc:                       # pragma: no cover - a role never kills it
            role_report = {"state": "ERROR", "why": f"{type(exc).__name__}: {str(exc)[:160]}"}

    # ---- the debt ledger again, so phase-1 and synthesis debt is persisted with its blockers.
    debt = {**retry_debt(reg, uni, mem, tallies["CONVERTER"], outputs, fp, limit=0,
                         write=not dry_run),
            "resolved_this_pass": debt["resolved_this_pass"],
            "retried_this_pass": debt["retried_this_pass"]}

    # ---- persist
    donated = None
    map_defect = ""
    if not dry_run:
        new_classes = {c["class"] for c in outputs["classes"]} - set(ontology)
        _save_ontology(new_classes, {c["class"]: c["lab"] for c in outputs["classes"]
                                     if c["class"] in new_classes})
        _append_jsonl(GENEALOGY, outputs["genealogy"])
        _append_jsonl(DATA_REQUESTS, outputs["data_requests"])
        known_q = {str(r.get("series")) for r in _jsonl(JEV_JOBS)}
        _append_jsonl(JEV_JOBS, [j for j in outputs["jev"] if j["series"] not in known_q])
        # THE EVIDENCE MAP FIRST (audit must-fix 4): the compiler may read a donation the moment
        # it lands, so the guard's start dates are on disk before any donation is.
        try:
            roles.record_evidence_start(outputs["donate"], STATE_DIR / "evidence_start.json")
        except roles.EvidenceMapUnreadable as exc:
            # No evidence date on disk means no donation (audit must-fix on 37bb136b4): a cell
            # the trim cannot find would be judged on its contaminated window.
            map_defect = f"EVIDENCE MAP UNREADABLE: {exc}; {len(outputs['donate'])} cell(s) " \
                         f"held, nothing donated"
            outputs["donate"] = []
        if outputs["donate"]:
            target = donation_target(DONATE_DIR)
            target.mkdir(parents=True, exist_ok=True)
            stamp = _now().replace(":", "").replace("-", "")[:15]
            donated = target / f"discoveries_{stamp}.json"
            _write_json(donated, {"source": ORGAN, "generated_at": _now(), "rule": RULE,
                                  "discoveries": outputs["donate"]})
        _write_json(MODELS, models)
        _count_calls(calls_made)
        # THE VERDICT LOOP: this pass's calls are charged to their lab and model, every verdict on
        # a lab cell is credited back, and the next pass ranks on certified k_eff per call.
        pairs = [(a.lab.key, a.model) for a in asks] if seat_on else []
        pairs += [(k, "") for k, t in tallies.items()
                  for _ in range(max(0, t.asked - sum(1 for a in asks if a.lab.key == k)))]
        try:
            credit = roles.verdict_loop(VERDICTS, DONATE_DIR,
                                        pairs[:calls_made] if calls_made else [],
                                        STATE_DIR / "verdict_credit.json", usage=usage)
        except Exception as exc:          # a broken credit file never loses the pass's report
            credit = {"error": f"verdict_loop: {type(exc).__name__}: {str(exc)[:160]}"}
    now_iso = _now()
    for mkey in pass_cov:
        rotation[mkey] = now_iso
    per_pass = int(share.get("per_pass") or 0) if share else 0
    window_h = (-(-len(registered) // per_pass) + 1) if per_pass else None
    if not dry_run:
        _write_json(ROTATION, rotation)
    coverage = roles.coverage_report(models, pass_cov, {k: t.row() for k, t in tallies.items()},
                                     role_report, cb_tone, credit, chain_status,
                                     seat_on=seat_on, dry_run=dry_run, rotation=rotation,
                                     window_h=window_h,
                                     budget_bound=bool(share) and calls_made >= calls_budget,
                                     collector=collector)
    coverage["openrouter_share"] = share or UNMEASURED
    if not dry_run:
        _write_json(STATE_DIR / "model_yield.json", coverage["models"])
        _write_json(REPORT.parent / "LLM_COVERAGE.json", coverage)
    states = coverage_from_outcomes(cov)
    if not dry_run:
        _write_json(COVERAGE, cov.doc)
    ont_after = _ontology() if not dry_run else ontology
    total_novelty: Counter = Counter()
    for t in tallies.values():
        total_novelty.update(t.novelty)
    jev_jobs = _jsonl(JEV_JOBS)
    doc: dict[str, Any] = {
        "generated_utc": _now(), "organ": ORGAN, "law": RULE,
        "verdict": ("RAN" if calls_made else UNMEASURED),
        "why": ("" if calls_made else
                "dry run" if dry_run else
                "no free provider resolves on this host (seat dark): the lab planned its pass, "
                "re-compiled its debt and kept every coordinate owed" if not seat_on else
                "daily call cap reached: the pass is owed"),
        "seat_enabled": seat_on, "free_chain": chain_status, "paid_enabled":
            os.environ.get("QUANT_LLM_LAB_PAID", "0") == "1",
        "openrouter_account": {
            "daily_free_limit": or_key.get("daily_limit") or UNMEASURED,
            "limit_source": or_key.get("limit_source") or UNMEASURED,
            "is_free_tier": or_key.get("is_free_tier", UNMEASURED),
            "credit_limit_usd": or_key.get("credit_limit_usd", UNMEASURED),
            "usage_usd": or_key.get("usage_usd", UNMEASURED),
            "paid_ids_refused": not openrouter_guard.paid_allowed()},
        "budget": {"max_calls_per_pass": max_calls, "daily_calls_cap": daily_cap,
                   "calls_this_pass": calls_made, "calls_left_today": _calls_left(daily_cap),
                   "budget_s": budget_s, "elapsed_s": round(time.time() - started, 1)},
        "labs": {k: {"name": LAB_BY_KEY[k].name if k in LAB_BY_KEY else k.lower(), **t.row()}
                 for k, t in tallies.items()},
        "plan": plan,
        "novelty": {c: int(total_novelty.get(c, 0)) for c in NOVELTY_CLASSES},
        "emitted": len(outputs["donate"]), "donation": _rel(donated) if donated else None,
        "independent_rediscoveries": redisc, "disagreements": disagree,
        "red_team_attacks": outputs["attacks"][:30],
        "referee_loop": {"refereed": len(outputs["referee"]),
                         "verdicts": dict(Counter(r["verdict"] for r in outputs["referee"])),
                         "revisions_emitted": tallies["REVISION"].emitted,
                         "reports": outputs["referee"][:20]},
        "conversion_debt": debt,
        "cb_tone": cb_tone,
        "collector": collector,
        "donations": donations,
        "roles": role_report,
        "model_coverage": {k: coverage.get(k) for k in ("verdict", "red", "models_available",
                                                  "models_answered")},
        "verdict_loop": {k: credit.get(k) for k in ("keff_basis", "judged_cells",
                                                    "certified_cells", "ranking_rule")},
        "funnel": {"rule": "ideas -> donated cells -> judged -> survivors (certified), "
                           "cumulative, each per compute-hour; a lab is its prompt family",
                   "labs": {k: (r or {}).get("funnel") for k, r in
                            (credit.get("labs") or {}).items()},
                   "models": {k: (r or {}).get("funnel") for k, r in
                              (credit.get("models") or {}).items()}},
        "data_requests_this_pass": len(outputs["data_requests"]),
        "market_share": market_share(a.coord for a in asks),
        "jev": {"provider": UNMEASURED,
                "why": ("no TypeSafe/Jev key is acquired and its current API is unverified; "
                        "questions queue and their cells wait as NEEDS_DATA until a Jev series "
                        "lands in the lake"),
                "queued_questions": sum(1 for j in jev_jobs if j.get("state") == "QUEUED")},
        "coverage": {**owed(cov, ont_after), "states": states,
                     "ontology_classes": len(ont_after),
                     "new_classes_this_pass": sorted({c["class"] for c in outputs["classes"]}
                                                     - set(ontology))[:40]},
        "models": {"registered": sum(1 for r in models.values()
                                     if r.get("status") == "REGISTERED"),
                   "review_pending": sum(1 for r in models.values()
                                         if r.get("status") == "REVIEW_PENDING"),
                   "hunted_this_pass": hunted[:20],
                   "top": sorted(({"model": k, "novel": r.get("novel", 0),
                                   "exact": r.get("exact", 0), "replies": r.get("replies", 0)}
                                  for k, r in models.items()),
                                 key=lambda r: (-int(r["novel"]), -int(r["exact"])))[:10]},
        "families_registered": len(reg), "universe_symbols": len(uni),
        "registry_fingerprint": fp,
    }
    if isinstance(donations, dict) and donations.get("red"):
        doc["red"] = True
        doc["defects"] = [donations.get("defect")]
    if LANE_POLICY_ERRORS:
        doc["red"] = True
        doc["defects"] = [*(doc.get("defects") or []),
                          "LANE POLICY UNREADABLE: every lane check failed closed this pass "
                          f"({'; '.join(f'{k}: {v}' for k, v in LANE_POLICY_ERRORS.items())})"]
    if map_defect:
        doc["red"] = True
        doc["defects"] = [*(doc.get("defects") or []), map_defect]
    if not dry_run:
        _write_json(REPORT, doc)
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's mode)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--max-calls", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, max_calls=a.max_calls, dry_run=a.dry_run, workers=a.workers)
    print(json.dumps({k: doc[k] for k in ("verdict", "why", "emitted", "novelty", "coverage",
                                          "conversion_debt")}, default=str)[:3000])
    for d in doc.get("defects") or []:
        print(f"LLM_LAB RED: {d}")
    return 1 if doc.get("red") and not a.dry_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
