"""DEEPSEEK THIRD-BRAIN LABORATORY -- the queue-driven 24/7 layer over `deepseek_cycle`.

WHAT THE HOURLY CYCLE WAS. One role per hour, one call, round-robin over 35 seed roles: a role came
round every day and a half whether or not it had ever produced anything, a provider error lost the
hour's work for good (the role pointer had already moved on), and a finding the model called an
EXACT_CANDIDATE reached the compiler WITHOUT `params` -- so `compile_row`'s EXACT_RECIPE door, which
admits only `family` + `params` + `symbols`, could never open for a DeepSeek row. Every DeepSeek
"exact" strategy was re-read from prose or parked in the deepening queue.

WHAT THIS ADDS (third-brain addendum sections 6-13, 21, 23-27, 32, 38), and only this:

  * A PERSISTENT JOB QUEUE (`data/deepseek_lab/queue.json`). Jobs carry stable ids, so a restart
    resumes them and an event seen twice enqueues once. A provider failure keeps the job PENDING
    with a backoff; nothing is dropped for being deferred.
  * LABS A-Q PLUS CONVERSION as data, each with a cadence (hourly / daily / weekly) and the packet
    sections it may see. Event jobs fire when a packet section's content hash changes.
  * JOB SCORING inside the lab: measured downstream yield per lab (compiled exact candidates and
    gauntlet passes per call), urgency, age and model tier cost, with a cold-exploration floor and
    a probation prior. This only orders DeepSeek's own jobs; the desk's department budget stays
    `research_auction.py`'s.
  * OUTPUT CONTRACT ds-2: exact rules, falsifier, data inputs, registered family + params (the
    `formula` family takes an `alpha_grammar` expression, which is how a new mechanism becomes an
    exact executable). Vague rules, unknown series, unregistered families and invalid expressions
    are named and downgraded, never repaired by invention. Banal indicator variants are rejected
    as discoveries.
  * FREEZE + NOVELTY + GENEALOGY: every exact candidate is hashed FROZEN_PRE_EVALUATION; exact
    duplicates are collapsed, parameter neighbours share one trial family, descendants keep their
    parents.
  * TYPED ROUTING into the SAME stores: exact candidates -> `data/intelligence/deepseek`
    (compiler EXACT_RECIPE -> docket -> gauntlet); hypotheses -> the same door (deepening queue);
    data and source requests -> the hunt frontier (NAMED_ONLY = priority ground for the hunters)
    and an open-request ledger that re-checks arrival; capability challengers -> the existing walk.
  * COVERAGE DEBT: each exact candidate's same-asset-class translations are registered as owed
    coordinates and drained by cursor; a cap means "not this pass", never "never".
  * FEEDBACK: compiler receipts and gate-ledger verdicts are joined back by hypothesis id and
    credited to lab, model and prompt version; the scores above read that ledger.
  * A SEAT REGISTRY of EVERY `:free` model of every family, refreshed from OpenRouter's public
    model list (paid ids are never registered). Each model is a named seat with its own yield:
    the first job of a cycle takes the least-called seat (coverage), the rest go to the best
    measured seats, and a failed seat falls through to the next with the attempt on the record.
    The job is credited to the seat that ANSWERED -- never a silent substitution. A loopback
    open-weight seat (any family) takes over when the cloud is out.

AUTHORITY. Research generation only. Nothing here promotes, sizes, certifies, arms or merges; the
fences in `deepseek_cycle` apply to every object, and model text is data, never instruction.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.ops import deepseek_cycle as ds

_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "ds-2"
PROMPT_VERSION = "lab-1"
STATE_DIR = "data/deepseek_lab"
QUEUE = f"{STATE_DIR}/queue.json"
ATTRIBUTION = f"{STATE_DIR}/attribution.json"
REQUESTS = f"{STATE_DIR}/requests.json"
DEBT = f"{STATE_DIR}/coverage_debt.json"
FROZEN = f"{STATE_DIR}/frozen.jsonl"
MODELS = f"{STATE_DIR}/models.json"
MARKS = f"{STATE_DIR}/event_marks.json"
FRONTIER = "desks/mt5/data/deep_forest_frontier.json"
COMPILER_OUT = "desks/mt5/data/hypotheses/miner_candidates.json"
DEEPEN_QUEUE = "desks/mt5/data/hypotheses/miner_deepening_queue.json"
GATE_LEDGER = "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl"

MODELS_URL = "https://openrouter.ai/api/v1/models"
MODELS_TTL_H = 6.0
GATE_TAIL = 50_000
MAX_ATTEMPTS = 8

# ------------------------------------------------------------------------------------- LABS
#
# Directive section 8, as data. `sections` is what the lab's cold context may carry: a lab sees the
# facts its question needs, not the whole packet, which keeps the prompt small and the cold
# phase focused. `cold` labs hold the exploration floor. `period_h` is the cadence; event jobs
# come on top of it.
LABS: dict[str, dict[str, Any]] = {
    "A": {"name": "unknown_unknown", "period_h": 1, "tier": "deep", "cold": True,
          "sections": ["universe", "data_and_features", "research_frontier"],
          "brief": "mechanism classes, participants, constraints and information channels ABSENT "
                   "from the current ontology; the assumption every current strategy shares; "
                   "edges viable only at small capital; newly emerged market structure"},
    "B": {"name": "economic_mechanism", "period_h": 1, "tier": "bulk", "cold": False,
          "sections": ["universe", "data_and_features", "research_frontier"],
          "brief": "forced transactions, hedging, inventory, rebalancing, benchmark flows, "
                   "funding, "
                   "carry, insurance demand, margin/liquidation, slow information diffusion. "
                   "Mechanism before parameter: who is forced, why they pay"},
    "C": {"name": "mathematical_stochastic", "period_h": 24, "tier": "deep", "cold": False,
          "sections": ["universe", "data_and_features"],
          "brief": "HMM/HSMM, GARCH family, jumps, Hawkes, filtering, first passage, survival, "
                   "spectral, causal discovery -- each must yield a measurable state, hazard, "
                   "residual or rule expressible as an alpha_grammar expression"},
    "D": {"name": "data_axis", "period_h": 1, "tier": "bulk", "cold": True,
          "sections": ["data_and_features", "point_in_time_metadata", "universe"],
          "brief": "which economically meaningful variable is NOT measured here? Emit DATA_REQUEST "
                   "objects with variable, mechanism, source classes, PIT needs, falsifier"},
    "E": {"name": "representation", "period_h": 1, "tier": "bulk", "cold": True,
          "sections": ["data_and_features", "universe"],
          "brief": "economically coherent transforms (change, rank, persistence, residual, spread, "
                   "dispersion, state-conditioned value) of data the desk HAS, written as "
                   "alpha_grammar expressions; never transforms for their own sake"},
    "F": {"name": "macro_global_cross_asset", "period_h": 24, "tier": "deep", "cold": False,
          "sections": ["universe", "data_and_features"],
          "brief": "participant -> incentive -> constraint -> flow -> transmission -> MT5 asset -> "
                   "horizon -> falsifier, across rates, FX, metals, energy, indices, regions. "
                   "data_and_features.futures_state lists futures/positioning/curve series: "
                   "condition an MT5 target on one with family exogenous_conditioner "
                   "(params source, signal, transform, threshold, side_when_high)"},
    "G": {"name": "news_event", "period_h": 24, "tier": "bulk", "cold": False,
          "sections": ["universe", "data_and_features"],
          "brief": "scheduled releases, surprises, revisions, central-bank communication; split "
                   "pre-event state, surprise, continuation, reversal; event-specific costs"},
    "H": {"name": "options_volatility", "period_h": 24, "tier": "deep", "cold": False,
          "sections": ["universe", "data_and_features"],
          "brief": "implied vs realized vol, VRP, skew, term structure, gamma/vanna/charm, expiry "
                   "concentration -- as conditioners of MT5-executable strategies; name the PIT "
                   "source or emit a DATA_REQUEST"},
    "I": {"name": "orderflow_microstructure", "period_h": 1, "tier": "bulk", "cold": False,
          "sections": ["universe", "data_and_features"],
          "brief": "quote intensity, tick imbalance, spread state, staleness, futures-to-CFD "
                   "transmission, markouts on OBSERVABLE data only; never invent L2"},
    "J": {"name": "execution", "period_h": 24, "tier": "bulk", "cold": False,
          "sections": ["universe", "portfolio_opportunity_state"],
          "brief": "entry timing, spread/event avoidance, stops/targets, time exits, cooldown -- "
                   "as testable variants, never as live changes"},
    "K": {"name": "sares_donor", "period_h": 24, "tier": "bulk", "cold": False,
          "sections": ["research_frontier", "conversion_inventory", "universe"],
          "brief": "mechanism FRAGMENTS from public traders, EAs, leaderboards; normalise away "
                   "leverage, martingale, survivorship, luck; independent descendants only"},
    "L": {"name": "failure_near_survivor", "period_h": 1, "tier": "bulk", "cold": False,
          "sections": ["research_frontier", "empirical_memory"],
          "brief": "classify failures (proxy, horizon, regime, sample, leakage, cost, decay, data, "
                   "validator false negative); descendants ONLY with a named enabling change"},
    "M": {"name": "survivor_decomposition", "period_h": 24, "tier": "deep", "cold": False,
          "sections": ["research_frontier", "portfolio_opportunity_state"],
          "brief": "which component carries a survivor's edge, where it should fail, which assets "
                   "express the same economics, its minimal description"},
    "N": {"name": "portfolio_complementarity", "period_h": 24, "tier": "bulk", "cold": False,
          "sections": ["portfolio_opportunity_state", "research_frontier", "universe"],
          "brief": "strategies valuable because they cover an uncovered regime, session or asset, "
                   "hedge a tail, or add effective breadth -- not standalone Sharpe"},
    "O": {"name": "validation_red_team", "period_h": 6, "tier": "deep", "cold": False,
          "sections": ["empirical_memory", "point_in_time_metadata"],
          "brief": "leakage, timestamps, revisions, survivorship, hidden trials, snooping, cost "
                   "and execution assumptions, lockbox contamination -> VALIDATION_ATTACK"},
    "P": {"name": "open_research_technology", "period_h": 168, "tier": "bulk", "cold": False,
          "sections": ["resource_state"],
          "brief": "public repos/models for program synthesis, symbolic regression, QD/MAP-Elites, "
                   "causal inference, local inference -> CAPABILITY_CHALLENGER with licence"},
    "Q": {"name": "meta_research", "period_h": 168, "tier": "deep", "cold": False,
          "sections": ["resource_state"],
          "brief": "which prompts, labs and models produce judgeable, novel, surviving work "
                   "(attribution is attached) -> RESEARCH_METHOD_CHALLENGER, shadow only"},
    "CONV": {"name": "raw_to_testable_conversion", "period_h": 1, "tier": "bulk", "cold": False,
             "sections": ["conversion_inventory", "universe", "data_and_features"],
             "brief": "turn queued raw findings and parked hypotheses into EXACT_CANDIDATE objects "
                      "with registered family + params; say NEEDS_DATA rather than invent"},
}
COLD_LABS = tuple(k for k, v in LABS.items() if v.get("cold"))

#: A packet section whose content hash changed creates a job for these labs (section 7, event).
SECTION_EVENTS: dict[str, tuple[str, ...]] = {
    "data_and_features": ("D", "E", "F", "H"),
    "research_frontier": ("L", "M"),
    "conversion_inventory": ("CONV",),
    "empirical_memory": ("L", "O"),
    "portfolio_opportunity_state": ("N",),
    "universe": ("I",),
}

#: Prior research value per lab before any measurement. Equal by default: a lab EARNS work through
#: the attribution ledger, not through its place in this list.
BASE_VALUE = 1.0
TIER_COST = {"bulk": 1.0, "deep": 3.0}

# ------------------------------------------------------------------------------- utilities


def _now_dt() -> datetime:
    return datetime.now(tz=UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _parse(ts: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _sha(obj: Any, n: int = 20) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()[:n]


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _save(path: Path, doc: Any) -> None:
    """Atomic: a crash mid-write leaves the previous queue, never half of one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
    tmp.replace(path)


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z][a-z0-9_]{2,}", str(text or "").lower())
            if t not in _STOP}


_STOP = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "when", "into", "over", "under",
    "than", "then", "are", "was", "were", "will", "can", "may", "its", "their", "they",
    "them", "which", "while", "where", "what", "who", "whom", "whose", "because", "between",
    "after", "before", "each", "every", "other", "same", "more", "less", "most", "least",
    "price", "prices", "market", "markets", "trade", "trades", "trading", "strategy",
})


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


# ------------------------------------------------------------------------------- the queue


def load_queue(root: Path) -> dict[str, Any]:
    q = _load(root / QUEUE, {})
    if not isinstance(q, dict) or not isinstance(q.get("jobs"), dict):
        q = {"jobs": {}, "created_utc": _iso(_now_dt())}
    return q


def save_queue(root: Path, q: dict[str, Any]) -> None:
    q["updated_utc"] = _iso(_now_dt())
    _save(root / QUEUE, q)


def enqueue(q: dict[str, Any], lab: str, trigger: str, subject: dict[str, Any] | None = None,
            *, now: datetime | None = None) -> str | None:
    """Add a job once. The id is a hash of (lab, trigger), so the same event seen by two cycles,
    or by a cycle and its restart, is one job. Returns the id when it was new."""
    if lab not in LABS:
        return None
    jid = "dsj_" + _sha([lab, trigger], 16)
    if jid in q["jobs"]:
        return None
    q["jobs"][jid] = {"job_id": jid, "lab": lab, "trigger": trigger, "subject": subject or {},
                      "created_utc": _iso(now or _now_dt()), "status": "PENDING",
                      "attempts": 0, "next_after_utc": None, "last_error": None}
    return jid


def ensure_cadence(q: dict[str, Any], *, now: datetime | None = None) -> list[str]:
    """One job per lab per cadence bucket. Bucket ids are wall-clock slots, so a box that was down
    for a day gets ONE catch-up job per lab, not twenty-four."""
    t = now or _now_dt()
    made = []
    for lab, spec in LABS.items():
        period = float(spec["period_h"])
        bucket = int(t.timestamp() // (period * 3600))
        jid = enqueue(q, lab, f"cadence:{period:g}h:{bucket}", {"cadence_h": period}, now=t)
        if jid:
            made.append(jid)
    return made


def scan_events(q: dict[str, Any], packet: dict[str, Any], marks: dict[str, Any], *,
                now: datetime | None = None) -> list[str]:
    """Section 7, event-driven: a packet section whose CONTENT changed (its hash, not the clock)
    enqueues the labs that research that change. The first sighting only records the mark --
    a cold start is not an event."""
    made = []
    sections = packet.get("sections") or {}
    seen = marks.setdefault("sections", {})
    for name, labs in SECTION_EVENTS.items():
        sec = sections.get(name)
        if not isinstance(sec, dict) or sec.get("status") == "UNMEASURED":
            continue
        h = _sha({k: v for k, v in sec.items() if k not in ("age_hours",)}, 16)
        prior = seen.get(name)
        seen[name] = h
        if prior is None or prior == h:
            continue
        for lab in labs:
            jid = enqueue(q, lab, f"event:{name}:{h}", {"section": name, "from": prior, "to": h},
                          now=now)
            if jid:
                made.append(jid)
    return made


def due_jobs(q: dict[str, Any], *, now: datetime | None = None) -> list[dict[str, Any]]:
    t = now or _now_dt()
    out = []
    for j in q["jobs"].values():
        if j.get("status") != "PENDING":
            continue
        na = _parse(j.get("next_after_utc"))
        if na and na > t:
            continue
        out.append(j)
    return out


def fail_job(job: dict[str, Any], why: str, *, now: datetime | None = None) -> None:
    """PROVIDER FAILURE PRESERVES THE JOB (section 39). Backoff doubles from 15 minutes to a
    six-hour ceiling; after MAX_ATTEMPTS the job is PARKED with its reason -- visible, never
    deleted, and re-armed by `rearm_parked` on the next healthy cycle."""
    t = now or _now_dt()
    job["attempts"] = int(job.get("attempts") or 0) + 1
    job["last_error"] = str(why)[:400]
    delay = min(6 * 60, 15 * 2 ** (job["attempts"] - 1))
    job["next_after_utc"] = _iso(t + timedelta(minutes=delay))
    if job["attempts"] >= MAX_ATTEMPTS:
        job["status"] = "PARKED"


def rearm_parked(q: dict[str, Any]) -> int:
    n = 0
    for j in q["jobs"].values():
        if j.get("status") == "PARKED":
            j["status"], j["attempts"], j["next_after_utc"] = "PENDING", 0, None
            n += 1
    return n


# ---------------------------------------------------------------------------- job scoring


def lab_rate(attrib: dict[str, Any], lab: str) -> tuple[float, str]:
    """Measured downstream usefulness per call, with a probation prior.

    useful = exact candidates the compiler admitted + gauntlet passes x 5 + accepted requests x
    0.25. A lab with fewer than three calls is on PROBATION at rate 1.0: a new lab earns its first
    work, then keeps it only by producing."""
    row = (attrib.get("by_lab") or {}).get(lab) or {}
    calls = int(row.get("calls") or 0)
    if calls < 3:
        return 1.0, "PROBATION"
    useful = (float(row.get("compiled") or 0) + 5.0 * float(row.get("passed") or 0)
              + 0.25 * float(row.get("requests") or 0))
    return (1.0 + useful) / (1.0 + calls), "MEASURED"


def score(job: dict[str, Any], attrib: dict[str, Any], *, now: datetime | None = None
          ) -> dict[str, Any]:
    """Priority = value x measured yield x urgency x age / tier cost (section 26, inside the lab).
    The terms are named on the job so the ordering can be audited."""
    t = now or _now_dt()
    lab = job["lab"]
    rate, basis = lab_rate(attrib, lab)
    trig = str(job.get("trigger") or "")
    urgency = 1.5 if trig.startswith("event:") else 1.2 if trig.startswith("resume:") else 1.0
    urgency *= 0.8 ** int(job.get("attempts") or 0)
    created = _parse(job.get("created_utc")) or t
    age = 1.0 + min(3.0, max(0.0, (t - created).total_seconds() / 86400.0))
    cost = TIER_COST.get(LABS[lab]["tier"], 1.0)
    p = BASE_VALUE * rate * urgency * age / cost
    return {"priority": round(p, 4), "rate": round(rate, 4), "basis": basis,
            "urgency": round(urgency, 3), "age": round(age, 3), "cost": cost}


def select(jobs: list[dict[str, Any]], attrib: dict[str, Any], k: int, *,
           now: datetime | None = None) -> list[dict[str, Any]]:
    """Top-k by priority, one job per lab per cycle, and a COLD FLOOR: when any cold-exploration
    job is due, at least one slot goes to it whatever the scores say (section 18)."""
    if k <= 0 or not jobs:
        return []
    for j in jobs:
        j["score"] = score(j, attrib, now=now)
    ranked = sorted(jobs, key=lambda j: (-j["score"]["priority"], j["created_utc"], j["job_id"]))
    picked: list[dict[str, Any]] = []
    labs: set[str] = set()
    cold = next((j for j in ranked if j["lab"] in COLD_LABS), None)
    if cold is not None:
        picked.append(cold)
        labs.add(cold["lab"])
    for j in ranked:
        if len(picked) >= k:
            break
        if j in picked or j["lab"] in labs:
            continue
        picked.append(j)
        labs.add(j["lab"])
    return picked[:k]


# --------------------------------------------------------------------- desk vocabulary


def _desk_paths(root: Path) -> None:
    for p in (str(root), str(root / "desks" / "mt5"), str(root / "desks" / "mt5" / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)


def universe(root: Path) -> dict[str, str]:
    """symbol -> asset class, from the registry the compiler and gauntlet read."""
    doc = _load(root / "desks/mt5/data/universe/universe.json", {})
    out = {}
    if isinstance(doc, dict):
        for k, v in doc.items():
            if isinstance(v, dict) and not str(k).startswith("_"):
                out[str(k)] = str(v.get("asset_class") or v.get("category") or "unknown")
    return out


def family_specs(root: Path) -> dict[str, list[str]]:
    """Registered executable families -> their tunable parameter names, read from the functions
    the gauntlet calls (`mt5desk.families` + `ORTHOGONAL_FAMILIES`). The contract offers exactly
    these, so an exact candidate is executable by construction rather than by hope."""
    _desk_paths(root)
    out: dict[str, list[str]] = {}
    try:
        from mt5desk import families, families_orthogonal
    except Exception:
        return out
    fns = {n[len("family_"):]: getattr(families, n) for n in dir(families)
           if n.startswith("family_") and callable(getattr(families, n))}
    fns.update({k: v for k, v in families_orthogonal.ORTHOGONAL_FAMILIES.items() if callable(v)})
    for name, fn in fns.items():
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        out[name] = [p.name for p in sig.parameters.values()
                     if p.kind == p.KEYWORD_ONLY and p.name not in ("drivers", "population")]
    return out


def grammar_vocab() -> dict[str, Any]:
    try:
        from libs.research import alpha_grammar as g
    except Exception:
        return {}
    return {"terminals": sorted(g.TERMINALS), "unary": sorted(g.UNARY),
            "binary": sorted(g.BINARY), "windowed": sorted(g.WINDOWED),
            "binary_windowed": sorted(g.BINARY_WINDOWED), "windows": list(g.WINDOWS),
            "max_depth": g.MAX_DEPTH}


def valid_expr(expr: Any) -> tuple[bool, str]:
    try:
        from libs.research import alpha_grammar as g
    except Exception as exc:
        return False, f"GRAMMAR_UNAVAILABLE: {exc}"
    try:
        tree = g.from_str(expr) if isinstance(expr, str) and "(" in expr else expr
    except ValueError as exc:
        return False, f"UNPARSEABLE_EXPR: {exc}"
    return (True, "") if g.is_valid(tree) else (False, "INVALID_EXPR (operator, window or depth)")


def known_series(root: Path, uni: dict[str, str]) -> set[str]:
    """Series the desk can actually supply: registry symbols, grammar terminals, and datasets in
    the data registry. Lower-cased. A data input outside this set is a DATA_REQUEST."""
    s = {k.lower() for k in uni}
    s |= {t.lower() for t in (grammar_vocab().get("terminals") or [])}
    reg = _load(root / "desks/mt5/data/data_registry.json", {})
    ds_ = reg.get("datasets") if isinstance(reg, dict) else None
    if isinstance(ds_, dict):
        s |= {str(k).lower() for k in ds_}
    elif isinstance(ds_, list):
        s |= {str(d.get("id") or d.get("name") or "").lower() for d in ds_ if isinstance(d, dict)}
    # The Futures lane's series ids (`exogenous_conditioner` `source` values) are suppliable.
    fut = _load(root / "desks/mt5/data/intelligence/futures_state/lab_inputs.json", {})
    for r in (fut.get("rows") or []) if isinstance(fut, dict) else []:
        if isinstance(r, dict) and r.get("series"):
            s.add(str(r["series"]).lower())
            s |= {f"{str(r['series']).lower()}.{str(c).lower()}" for c in r.get("columns") or []}
    s.discard("")
    return s


# ------------------------------------------------------------------- the contract (ds-2)

VAGUE = ("strong trend", "large move", "good momentum", "institutional buying", "obvious support",
         "significant breakout", "strong momentum", "big move", "clear trend", "smart money",
         "oversold enough", "high probability")
#: Indicator rules that are baselines, not discoveries (section 16). Rejected as NEW unless the
#: object names a new data input or a mechanism class the desk has not got.
BANAL = ("rsi", "macd", "bollinger", "moving average cross", "ma cross", "sma cross",
         "ema cross", "golden cross", "death cross", "stochastic oscillator")
EXACT_REQUIRED = ("entry_rule", "exit_rule", "stop_rule", "falsifier", "holding_horizon",
                  "economic_mechanism")
FROZEN_FIELDS = ("symbols", "family", "params", "timeframe", "session", "direction",
                 "entry_rule", "exit_rule", "stop_rule", "target_rule", "holding_horizon",
                 "data_inputs", "execution_assumptions")


def contract_text(fams: dict[str, list[str]], vocab: dict[str, Any]) -> str:
    fam_lines = "; ".join(f"{k}({','.join(v)})" for k, v in sorted(fams.items()))
    return (
        f"OUTPUT CONTRACT {SCHEMA_VERSION}. Return ONLY JSON: {{\"objects\": [ ... ]}}. "
        "Every object "
        f"has \"object_type\" in {list(ds.OBJECT_TYPES)}, a \"title\", and the fields its type "
        "needs. No prose outside JSON. [] is an honest answer.\n"
        "EXACT_CANDIDATE needs: symbols (registry spelling), family + params from the REGISTERED "
        f"FAMILIES below, timeframe (M5|M15|M30|H1), session (all|asia|london|ny), direction, "
        f"{', '.join(EXACT_REQUIRED)}, forced_actor, why_they_pay, data_inputs [{{series_id, "
        "source, available_time_required, vintage_required}}], expected_failure_mode, "
        "alternative_explanations, mechanism_class, parent_ids (ids you descend from, else []).\n"
        "A NEW mechanism is made exact with family \"formula\": params {expr, norm, entry_z, "
        "side_mode (follow|fade), hold_bars, stop_atr, rr} where expr is an alpha_grammar "
        f"expression. Grammar: terminals {vocab.get('terminals')}; unary {vocab.get('unary')}; "
        f"binary {vocab.get('binary')}; windowed op(x, w) {vocab.get('windowed')}; binary "
        f"windowed op(x, y, w) {vocab.get('binary_windowed')}; w in {vocab.get('windows')}; "
        f"depth <= {vocab.get('max_depth')}. "
        "Example: mul(sign(delta(close, 5)), ts_rank(vol, 48)).\n"
        f"REGISTERED FAMILIES: {fam_lines}\n"
        "Rules must be deterministic and measurable. Words like 'strong trend' or 'large move' "
        "without a number are refused. Generic RSI/MACD/Bollinger/MA-cross rules are baselines, "
        "not discoveries. If you cannot make it exact, emit MECHANISM_HYPOTHESIS or "
        "DEEPENING_TASK; if the data is missing, emit DATA_REQUEST {variable, mechanism, "
        "source_classes, pit_requirements, expected_consumers, falsifier, priority}. "
        "REPRESENTATION_REQUEST {representation, inputs, expr (if expressible), mechanism}. "
        "VALIDATION_ATTACK {target, attack, evidence_needed, cheapest_decisive_test}. "
        "NEGATIVE_KNOWLEDGE {claim, why_dead}. Never invent fields to force testability."
    )


def lab_prompt(lab: str, job: dict[str, Any], cold: dict[str, Any], contract: str
               ) -> tuple[str, str]:
    spec = LABS[lab]
    system = (
        "You are DeepSeek, the quant desk's THIRD research brain: an independent cold-phase "
        "generator, never a decider. You cannot promote, size, certify, arm or merge anything; "
        "every object you return enters the desk's one canonical compiler and gauntlet. Execution "
        "universe: MT5/Fusion CFDs only. Information universe: any lawful public source.\n"
        f"LAB {lab} ({spec['name']}): {spec['brief']}.\n"
        f"JOB: {job.get('trigger')} {json.dumps(job.get('subject') or {}, default=str)[:600]}\n"
        "Be reckless in the questions, exact in the rules.\n\n" + contract)
    ctx = cold.get("cold_context") or {}
    keep = {k: v for k, v in (ctx.get("sections") or {}).items() if k in spec["sections"]}
    body = json.dumps({"packet_hash": ctx.get("packet_hash"), "sections": keep}, default=str,
                      indent=1)
    if len(body) > 14000:
        body = body[:14000] + "\n... TRUNCATED"
    return system, "COLD FACTS (no other agent's conclusion is present):\n" + body


def parse_objects(text: str) -> tuple[list[dict[str, Any]], str]:
    """JSON out of a model reply. A fenced block or a leading sentence is tolerated; anything that
    still does not parse is SCHEMA_INVALID with zero objects -- never a crash, never a guess."""
    s = str(text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    if not s.startswith("{") and "{" in s:
        s = s[s.index("{"):]
    try:
        doc = json.loads(s)
    except ValueError:
        return [], "SCHEMA_INVALID"
    objs = doc.get("objects", doc.get("findings")) if isinstance(doc, dict) else None
    if not isinstance(objs, list):
        return [], "SCHEMA_INVALID"
    return [o for o in objs if isinstance(o, dict)], "OK"


def _vague(text: str) -> str | None:
    low = str(text or "").lower()
    for v in VAGUE:
        if v in low and not re.search(r"\d", low):
            return v
    return None


def _banal(obj: dict[str, Any], known: set[str]) -> bool:
    blob = " ".join(str(obj.get(k) or "") for k in ("title", "entry_rule", "family",
                                                     "mechanism_class")).lower()
    if not any(b in blob for b in BANAL):
        return False
    inputs = [str((d or {}).get("series_id") or "").lower() for d in obj.get("data_inputs") or []
              if isinstance(d, dict)]
    exotic = [i for i in inputs if i and i not in {"close", "open", "high", "low", "ret", "vol"}]
    return not exotic


def validate(obj: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """One object -> normalised record with `object_type`, `disposition` and named `reasons`.

    Nothing is invented. A missing rule downgrades the object; an unknown series becomes a data
    request; an unregistered family becomes NEEDS_NEW_EXECUTABLE_FAMILY."""
    o = dict(obj)
    t = str(o.get("object_type") or o.get("type") or "").strip().upper()
    if t not in ds.OBJECT_TYPES:
        t = "MECHANISM_HYPOTHESIS"
    reasons: list[str] = []
    syms = [str(s).strip() for s in (o.get("symbols") or []) if str(s).strip()] \
        if isinstance(o.get("symbols"), list) else []
    uni: dict[str, str] = ctx["universe"]
    fold = {k.lower(): k for k in uni}
    resolved = [fold[s.lower()] for s in syms if s.lower() in fold]
    unknown_syms = [s for s in syms if s.lower() not in fold]
    o["symbols"] = resolved
    if unknown_syms:
        reasons.append(f"UNKNOWN_SYMBOLS:{unknown_syms[:5]}")
    disposition = "NEEDS_RULE_EXTRACTION"
    data_requests: list[dict[str, Any]] = []

    if t in ("EXACT_CANDIDATE", "FAILURE_DESCENDANT", "SURVIVOR_DESCENDANT") and \
            (o.get("family") or o.get("entry_rule")):
        missing = [f for f in EXACT_REQUIRED if not str(o.get(f) or "").strip()]
        fam = str(o.get("family") or "").strip()
        params = o.get("params") if isinstance(o.get("params"), dict) else None
        fams: dict[str, list[str]] = ctx["families"]
        for f in ("entry_rule", "exit_rule", "stop_rule", "target_rule"):
            v = _vague(str(o.get(f) or ""))
            if v:
                reasons.append(f"VAGUE_RULE:{f}:{v}")
        for d in o.get("data_inputs") or []:
            sid = str((d or {}).get("series_id") or "").strip() if isinstance(d, dict) else ""
            if sid and sid.lower() not in ctx["series"]:
                data_requests.append({"object_type": "DATA_REQUEST", "variable": sid,
                                      "source": (d or {}).get("source"),
                                      "mechanism": o.get("economic_mechanism"),
                                      "falsifier": o.get("falsifier"),
                                      "title": f"data for {o.get('title') or sid}"[:200]})
        if missing:
            reasons.append(f"MISSING:{missing}")
        if fam and fam not in fams:
            reasons.append(f"UNREGISTERED_FAMILY:{fam}")
        elif params is not None and fam:
            extra = sorted(set(params) - set(fams.get(fam) or []) - {"timeframe", "session"})
            if extra:
                reasons.append(f"UNKNOWN_PARAMS:{extra}")
            if fam == "formula":
                ok, why = valid_expr(params.get("expr"))
                if not ok:
                    reasons.append(why)
            if fam == "exogenous_conditioner":
                src = str(params.get("source") or "").strip()
                if not src:
                    reasons.append("MISSING:['params.source']")
                elif src.lower() not in ctx["series"]:
                    data_requests.append({"object_type": "DATA_REQUEST", "variable": src,
                                          "mechanism": o.get("economic_mechanism"),
                                          "falsifier": o.get("falsifier"),
                                          "title": f"series {src} for {o.get('title')}"[:200]})
        if _banal(o, ctx["series"]):
            t, disposition = "NEGATIVE_KNOWLEDGE", "INVALID"
            reasons.append("BANAL_INDICATOR_VARIANT")
        elif data_requests:
            disposition = "NEEDS_DATA"
        elif any(r.startswith("UNREGISTERED_FAMILY") for r in reasons):
            disposition = "NEEDS_NEW_EXECUTABLE_FAMILY"
        elif not resolved or params is None or any(
                r.startswith(("VAGUE", "MISSING", "UNKNOWN_PARAMS", "INVALID_EXPR",
                              "UNPARSEABLE", "GRAMMAR_UNAVAILABLE")) for r in reasons):
            disposition = "NEEDS_RULE_EXTRACTION"
        else:
            disposition = "TESTABLE_NOW"
        if disposition != "TESTABLE_NOW" and t == "EXACT_CANDIDATE":
            t = "MECHANISM_HYPOTHESIS"
    elif t == "DATA_REQUEST" or t == "SOURCE_ACQUISITION_REQUEST":
        if not str(o.get("variable") or o.get("source") or o.get("title") or "").strip():
            disposition = "INVALID"
            reasons.append("EMPTY_REQUEST")
        else:
            disposition = "NEEDS_DATA"
    elif t == "REPRESENTATION_REQUEST":
        expr = (o.get("expr") or (o.get("params") or {}).get("expr")
                if isinstance(o.get("params"), dict) or o.get("expr") else None)
        disposition = "NEEDS_REPRESENTATION"
        if expr:
            ok, why = valid_expr(expr)
            if ok and resolved:
                disposition = "TESTABLE_NOW"
                o.update({"family": "formula", "params": {"expr": expr}})
            elif not ok:
                reasons.append(why)
    elif t == "NEGATIVE_KNOWLEDGE":
        disposition = "TESTED" if str(o.get("why_dead") or "").strip() else "INVALID"
    elif t == "VALIDATION_ATTACK":
        disposition = ("BLOCKED" if not str(o.get("attack") or "").strip()
                       else "NEEDS_RULE_EXTRACTION")
    elif t in ("CAPABILITY_CHALLENGER", "RESEARCH_METHOD_CHALLENGER"):
        disposition = "NEEDS_NEW_EXECUTABLE_FAMILY"
    elif t == "DEEPENING_TASK":
        disposition = "NEEDS_RULE_EXTRACTION"
    if not str(o.get("title") or "").strip():
        disposition = "INVALID"
        reasons.append("NO_TITLE")
    o["object_type"], o["disposition"], o["reasons"] = t, disposition, reasons
    o["schema_version"] = SCHEMA_VERSION
    return {"object": o, "data_requests": data_requests}


# ---------------------------------------------------- freeze, novelty and genealogy


def _frozen_view(o: dict[str, Any]) -> dict[str, Any]:
    v = {k: o.get(k) for k in FROZEN_FIELDS if o.get(k) not in (None, "", [], {})}
    v["symbols"] = sorted(v.get("symbols") or [])
    return v


def load_memory(root: Path) -> list[dict[str, Any]]:
    out = []
    try:
        with (root / FROZEN).open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("hypothesis_id"):
                    out.append(r)
    except OSError:
        pass
    return out


def novelty(o: dict[str, Any], memory: list[dict[str, Any]]) -> dict[str, Any]:
    """Section 15. Compared against every frozen DeepSeek hypothesis before anything is tested.

    EXACT_DUPLICATE        same frozen rules (any lab, any model): one discovery, not two
    CROSS_ASSET_TRANSLATION same family + params, other symbols: same trial family
    PARAMETER_NEIGHBOUR    same family + symbols + mechanism class, other params: same family
    MECHANISM_NEIGHBOUR    mechanism wording overlaps >= 0.55 (Jaccard on content tokens)
    COMPOSITIONAL_DESCENDANT names parents
    GENUINELY_NOVEL        none of the above"""
    fv = _frozen_view(o)
    rule_sig = _sha(fv)
    fam = str(o.get("family") or "")
    fp_sig = _sha([fam, o.get("params")]) if fam else None
    nb_sig = _sha([fam, sorted(o.get("symbols") or []), str(o.get("mechanism_class") or "")]) \
        if fam else None
    toks = _tokens(f"{o.get('economic_mechanism') or o.get('mechanism') or ''} "
                   f"{o.get('forced_actor') or ''} {o.get('title') or ''}")
    best, best_sim = None, 0.0
    for m in memory:
        if m.get("rule_sig") == rule_sig and fv.get("family"):
            return {"class": "EXACT_DUPLICATE", "of": m["hypothesis_id"],
                    "trial_family_id": m.get("trial_family_id"), "rule_sig": rule_sig}
        if fp_sig and m.get("fp_sig") == fp_sig:
            return {"class": "CROSS_ASSET_TRANSLATION", "of": m["hypothesis_id"],
                    "trial_family_id": m.get("trial_family_id"), "rule_sig": rule_sig}
        if nb_sig and m.get("nb_sig") == nb_sig:
            return {"class": "PARAMETER_NEIGHBOUR", "of": m["hypothesis_id"],
                    "trial_family_id": m.get("trial_family_id"), "rule_sig": rule_sig}
        sim = _jaccard(toks, set(m.get("tokens") or []))
        if sim > best_sim:
            best, best_sim = m, sim
    if best is not None and best_sim >= 0.55:
        return {"class": "MECHANISM_NEIGHBOUR", "of": best["hypothesis_id"],
                "similarity": round(best_sim, 3),
                "trial_family_id": best.get("trial_family_id"), "rule_sig": rule_sig}
    parents = [p for p in (o.get("parent_ids") or []) if isinstance(p, str) and p]
    tf = "dstf_" + _sha([fam, sorted(toks)[:24]], 16)
    return {"class": "COMPOSITIONAL_DESCENDANT" if parents else "GENUINELY_NOVEL",
            "of": parents[0] if parents else None, "trial_family_id": tf, "rule_sig": rule_sig,
            "nearest_similarity": round(best_sim, 3)}


def freeze(root: Path, o: dict[str, Any], nov: dict[str, Any], prov: dict[str, Any]
           ) -> dict[str, Any]:
    """FROZEN_PRE_EVALUATION (section 24). The id IS the hash of the frozen rules, so a later edit
    is a new hypothesis by construction; the frozen view is written before any routing."""
    fv = _frozen_view(o)
    hid = "dsh_" + _sha(fv)
    fam = str(o.get("family") or "")
    row = {"hypothesis_id": hid, "frozen_hash": _sha(fv, 64), "frozen": fv,
           "status": "FROZEN_PRE_EVALUATION", "frozen_utc": _iso(_now_dt()),
           "rule_sig": nov["rule_sig"],
           "fp_sig": _sha([fam, o.get("params")]) if fam else None,
           "nb_sig": _sha([fam, sorted(o.get("symbols") or []),
                           str(o.get("mechanism_class") or "")]) if fam else None,
           "tokens": sorted(_tokens(f"{o.get('economic_mechanism') or o.get('mechanism') or ''} "
                                    f"{o.get('forced_actor') or ''} {o.get('title') or ''}"))[:64],
           "trial_family_id": nov.get("trial_family_id"),
           "parent_ids": [p for p in (o.get("parent_ids") or []) if isinstance(p, str)],
           "novelty": nov["class"], "object_type": o["object_type"],
           "disposition": o["disposition"], **prov}
    _append(root / FROZEN, row)
    return row


# ---------------------------------------------------------------------------- routing


def _donation_row(o: dict[str, Any], hid: str, tfid: str | None, lab: str) -> dict[str, Any]:
    params = dict(o.get("params") or {}) if isinstance(o.get("params"), dict) else None
    if params is not None:
        for axis in ("timeframe", "session"):
            if o.get(axis) and axis not in params and str(o.get(axis)).lower() not in ("all", "h1"):
                params[axis] = o[axis]
    row = {"source": "deepseek", "title": str(o.get("title") or "")[:300],
           "symbols": o.get("symbols") or [], "type": o["object_type"],
           "disposition": o["disposition"], "family": o.get("family"),
           "mechanism": str(o.get("economic_mechanism") or o.get("mechanism") or "")[:2000],
           "testable_claim": str(o.get("falsifier") or o.get("testable_claim") or "")[:2000],
           "entry_rule": o.get("entry_rule"), "exit_rule": o.get("exit_rule"),
           "stop_rule": o.get("stop_rule"), "holding_horizon": o.get("holding_horizon"),
           "mechanism_tags": [t for t in [o.get("family"), o.get("mechanism_class")] if t],
           "kind": "exact_recipe" if o["disposition"] == "TESTABLE_NOW" else "hypothesis",
           "url": f"deepseek://{lab}/{hid}", "hypothesis_id": hid,
           "lineage": {"root": hid, "trial_family_id": tfid,
                       "parents": [p for p in (o.get("parent_ids") or []) if isinstance(p, str)]}}
    if params is not None and o["disposition"] == "TESTABLE_NOW":
        row["params"] = params
    if o.get("parent_ids"):
        row["parent_ids"] = o["parent_ids"]
    return row


def donate(root: Path, rows: list[dict[str, Any]], tag: str) -> Path | None:
    """Into `data/intelligence/deepseek/` -- the tree `miner_candidate_compiler` reads -- in the
    miner-discovery contract, PIT-stamped by the shared stamper. No new admission path."""
    if not rows:
        return None
    from libs.data.pit import stamp_or_refuse
    stamped, refused = stamp_or_refuse(rows, "deepseek")
    if refused:
        raise ValueError(f"DeepSeek refused {len(refused)} unstamped discoveries")
    out = root / ds.DONATE_DIR
    out.mkdir(parents=True, exist_ok=True)
    stamp = _iso(_now_dt()).replace(":", "").replace("-", "")[:15]
    path = out / f"discoveries_{stamp}_{_sha(tag, 6)}.json"
    _save(path, {"source": "deepseek", "lab_tag": tag, "schema_version": SCHEMA_VERSION,
                 "generated_at": _iso(_now_dt()), "discoveries": stamped})
    return path


def _requests(root: Path) -> dict[str, Any]:
    r = _load(root / REQUESTS, {})
    if not isinstance(r, dict) or not isinstance(r.get("open"), dict):
        r = {"open": {}, "closed": {}}
    return r


def file_request(root: Path, o: dict[str, Any], prov: dict[str, Any]) -> str:
    """DATA / SOURCE / REPRESENTATION requests and VALIDATION ATTACKS: an open ledger that the
    lab re-checks every cycle (arrival closes a data request and resumes its parent), plus, for
    data and sources, a NAMED_ONLY vector on the hunt frontier -- which the hunters treat as
    priority ground, never as covered."""
    reqs = _requests(root)
    t = o["object_type"]
    key = str(o.get("variable") or o.get("representation") or o.get("target") or
              o.get("source") or o.get("title") or "").strip()
    rid = "dsr_" + _sha([t, key.lower()], 14)
    if rid not in reqs["open"] and rid not in reqs["closed"]:
        reqs["open"][rid] = {"request_id": rid, "object_type": t, "key": key[:200],
                             "title": str(o.get("title") or key)[:300],
                             "mechanism": str(o.get("mechanism") or o.get("economic_mechanism")
                                              or "")[:1000],
                             "falsifier": str(o.get("falsifier") or "")[:500],
                             "source_classes": o.get("source_classes") or o.get("source"),
                             "pit_requirements": o.get("pit_requirements"),
                             "attack": o.get("attack"), "test": o.get("cheapest_decisive_test"),
                             "parent_hypothesis": o.get("parent_hypothesis"),
                             "opened_utc": _iso(_now_dt()), "status": "OPEN", **prov}
    elif rid in reqs["open"] and o.get("parent_hypothesis"):
        reqs["open"][rid].setdefault("also_for", []).append(o["parent_hypothesis"])
    _save(root / REQUESTS, reqs)
    if t in ("DATA_REQUEST", "SOURCE_ACQUISITION_REQUEST") and key:
        try:
            from libs.research import hunt_frontier as hf
            path = root / FRONTIER
            st = hf.load(path)
            name = f"deepseek data request: {key}"[:160]
            if name not in st.vectors:
                hf.record(st, name, outcome="NAMED_ONLY", region="deepseek_data_request")
                hf.save(st, path)
        except Exception:
            pass
    return rid


def recheck_requests(root: Path, series: set[str], q: dict[str, Any]) -> list[str]:
    """Section 11: data arrives -> conversion resumes. A data request whose variable now names a
    series the desk supplies is CLOSED and its parent hypotheses get a resume job."""
    reqs = _requests(root)
    closed = []
    for rid, r in list(reqs["open"].items()):
        if r.get("object_type") != "DATA_REQUEST":
            continue
        if str(r.get("key") or "").lower() in series:
            r["status"], r["closed_utc"] = "ARRIVED", _iso(_now_dt())
            reqs["closed"][rid] = reqs["open"].pop(rid)
            for parent in [r.get("parent_hypothesis"), *(r.get("also_for") or [])]:
                if parent:
                    enqueue(q, "CONV", f"resume:{parent}", {"hypothesis_id": parent,
                                                           "arrived": r.get("key")})
            closed.append(rid)
    if closed:
        _save(root / REQUESTS, reqs)
    return closed


def register_debt(root: Path, o: dict[str, Any], hid: str, tfid: str | None,
                  uni: dict[str, str]) -> int:
    """Section 13. The same exact rule on every other registry symbol of its asset class is an
    OWED coordinate with a stable id. Registering costs nothing; draining is capped per pass."""
    debt = _load(root / DEBT, {})
    if not isinstance(debt, dict) or not isinstance(debt.get("coords"), dict):
        debt = {"coords": {}}
    syms = set(o.get("symbols") or [])
    classes = {uni.get(s) for s in syms} - {None, "unknown"}
    n = 0
    for sym, cls in sorted(uni.items()):
        if cls not in classes or sym in syms:
            continue
        cid = "dsc_" + _sha([hid, sym], 16)
        if cid in debt["coords"]:
            continue
        debt["coords"][cid] = {"coord_id": cid, "parent": hid, "trial_family_id": tfid,
                               "symbol": sym, "family": o.get("family"),
                               "params": o.get("params"), "title": o.get("title"),
                               "mechanism": o.get("economic_mechanism"),
                               "status": "OWED", "registered_utc": _iso(_now_dt())}
        n += 1
    _save(root / DEBT, debt)
    return n


def drain_debt(root: Path, limit: int) -> dict[str, Any]:
    """Donate up to `limit` owed translations. The rest stay OWED -- a cap is 'not this pass',
    never 'never'.

    ORDER IS THE ECONOMICS. A translation is worth judging once its PARENT has a gauntlet verdict:
    a passed parent's translations go first (where else does the mechanism pay?), a judged-failed
    parent's next (does it fail everywhere, or only there?), and an unjudged parent's wait --
    twenty-eight cells for an idea nobody has tested yet would spend the judge, the binding
    bottleneck, on the cheapest-to-defer work. Waiting coordinates are counted, never dropped."""
    debt = _load(root / DEBT, {})
    coords = debt.get("coords") if isinstance(debt, dict) else None
    if not isinstance(coords, dict):
        return {"owed": 0, "donated": 0, "awaiting_parent_verdict": 0}
    verdicts = ((_load(root / ATTRIBUTION, {}).get("gauntlet") or {}).get("verdicts") or {})
    owed_all = [c for c in coords.values() if c.get("status") == "OWED"]
    ready = [c for c in owed_all if c.get("parent") in verdicts]
    ready.sort(key=lambda c: (-int(bool((verdicts.get(c["parent"]) or {}).get("passed"))),
                              c.get("registered_utc") or "", c["coord_id"]))
    owed = ready
    rows = []
    for c in owed[:max(0, limit)]:
        rows.append({"source": "deepseek", "title": f"{c.get('title')} [{c['symbol']}]"[:300],
                     "symbols": [c["symbol"]], "family": c.get("family"),
                     "params": c.get("params") or {}, "type": "EXACT_CANDIDATE",
                     "disposition": "TESTABLE_NOW", "kind": "exact_recipe",
                     "mechanism": str(c.get("mechanism") or "")[:2000],
                     "operator": "cross_asset_translation",
                     "url": f"deepseek://debt/{c['parent']}/{c['coord_id']}",
                     "hypothesis_id": c["parent"],
                     "lineage": {"root": c["parent"], "trial_family_id": c.get("trial_family_id"),
                                 "parents": [c["parent"]], "operator": "cross_asset_translation"}})
        c["status"], c["donated_utc"] = "DONATED", _iso(_now_dt())
    path = donate(root, rows, "coverage_debt") if rows else None
    _save(root / DEBT, debt)
    left = len(owed) - len(rows)
    return {"owed": len(owed_all) - len(rows), "donated": len(rows),
            "awaiting_parent_verdict": len(owed_all) - len(ready),
            "path": str(path) if path else None,
            "drain_cycles_at_this_rate": (math.ceil(left / limit) if limit > 0 else None)}


def route(root: Path, recs: list[dict[str, Any]], *, lab: str, prov: dict[str, Any],
          ctx: dict[str, Any], memory: list[dict[str, Any]]) -> dict[str, Any]:
    """Every validated object gets exactly one disposition and one destination (section 21)."""
    donations: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    receipts: list[dict[str, Any]] = []

    def bump(k: str) -> None:
        counts[k] = counts.get(k, 0) + 1

    for rec in recs:
        o = rec["object"]
        t, disp = o["object_type"], o["disposition"]
        nov = novelty(o, memory)
        if nov["class"] == "EXACT_DUPLICATE":
            bump("duplicate")
            _append(root / FROZEN, {"sighting_of": nov["of"], "lab": lab, **prov,
                                    "at": _iso(_now_dt())})
            receipts.append({"title": o.get("title"), "route": "DUPLICATE", "of": nov["of"]})
            continue
        frozen = freeze(root, o, nov, {**prov, "lab": lab})
        memory.append(frozen)
        hid, tfid = frozen["hypothesis_id"], frozen["trial_family_id"]
        _append(root / ds.EVIDENCE, {"ts": _iso(_now_dt()), "lab": lab, "hypothesis_id": hid,
                                     "trial_family_id": tfid, "novelty": nov["class"],
                                     "type": t, "disposition": disp, "reasons": o["reasons"],
                                     "title": str(o.get("title") or "")[:300],
                                     "object": o, **prov})
        for dr in rec["data_requests"]:
            dr["parent_hypothesis"] = hid
            file_request(root, dr, prov)
            bump("data_request")
        if disp == "INVALID":
            bump("invalid")
            receipts.append({"hypothesis_id": hid, "route": "NEGATIVE_MEMORY",
                             "reasons": o["reasons"]})
            continue
        if t in ("DATA_REQUEST", "SOURCE_ACQUISITION_REQUEST", "VALIDATION_ATTACK") or \
                (t == "REPRESENTATION_REQUEST" and disp != "TESTABLE_NOW"):
            rid = file_request(root, o, prov)
            bump(t.lower())
            receipts.append({"hypothesis_id": hid, "route": "REQUEST_LEDGER", "request_id": rid})
            continue
        if t in ("CAPABILITY_CHALLENGER", "RESEARCH_METHOD_CHALLENGER"):
            walk = ds._propose_capability_walk(
                name=str(o.get("title")), source=str(o.get("source") or o.get("repository")
                                                     or "deepseek"),
                mechanism=str(o.get("mechanism") or o.get("economic_mechanism") or ""),
                evidence_grade=o.get("evidence_grade"), root=root)
            bump("challenger")
            receipts.append({"hypothesis_id": hid, "route": "CAPABILITY_WALK",
                             "status": walk.get("status")})
            continue
        if t == "NEGATIVE_KNOWLEDGE":
            bump("negative")
            receipts.append({"hypothesis_id": hid, "route": "NEGATIVE_MEMORY"})
            continue
        donations.append(_donation_row(o, hid, tfid, lab))
        if disp == "TESTABLE_NOW":
            bump("exact")
            if nov["class"] != "PARAMETER_NEIGHBOUR":
                bump_n = register_debt(root, o, hid, tfid, ctx["universe"])
                counts["debt_registered"] = counts.get("debt_registered", 0) + bump_n
            receipts.append({"hypothesis_id": hid, "route": "COMPILER_EXACT_RECIPE",
                             "novelty": nov["class"]})
        else:
            bump("deepening")
            receipts.append({"hypothesis_id": hid, "route": "COMPILER_DEEPENING",
                             "disposition": disp})
    path = donate(root, donations, lab)
    return {"counts": counts, "receipts": receipts, "donated_to": str(path) if path else None}


# ------------------------------------------------------------------------- the models


def _get_json(url: str, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-deepseek-lab/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def model_family(model_id: str) -> str:
    """The seat family: the provider prefix of an OpenRouter id, `local` for a loopback model."""
    mid = str(model_id or "")
    if mid.startswith("local/"):
        return "local"
    return mid.split("/", 1)[0] if "/" in mid else "?"


def refresh_models(root: Path, *, fetch: Callable[[str], Any] | None = None,
                   now: datetime | None = None) -> dict[str, Any]:
    """Section 27. OpenRouter's PUBLIC model list (no key is sent), cached for MODELS_TTL_H.

    EVERY `:free` id of EVERY family is a seat (zuck: "this doesnt literally mean deepseek but our
    llm factory lab" + every :free model each cycle). Paid ids are never registered, so a paid
    route cannot be reached from here even by a stale pin."""
    t = now or _now_dt()
    path = root / MODELS
    cached = _load(path, {})
    at = _parse(cached.get("fetched_utc")) if isinstance(cached, dict) else None
    if at and (t - at) < timedelta(hours=MODELS_TTL_H) and cached.get("models"):
        return dict(cached)
    try:
        doc = (fetch or _get_json)(MODELS_URL)
        rows = doc.get("data") if isinstance(doc, dict) else None
        if not isinstance(rows, list):
            raise ValueError("no data list")
    except Exception as exc:
        out = dict(cached) if isinstance(cached, dict) else {}
        out.update({"status": "UNMEASURED" if not out.get("models") else "STALE",
                    "last_error": f"{type(exc).__name__}: {str(exc)[:200]}",
                    "attempted_utc": _iso(t)})
        _save(path, out)
        return out
    models = []
    for m in rows:
        mid = str((m or {}).get("id") or "")
        if not mid.endswith(":free"):
            continue
        params = m.get("supported_parameters") or []
        low = mid.lower()
        models.append({"id": mid, "family": model_family(mid), "free": True,
                       "context_length": m.get("context_length"),
                       "reasoning": ("reasoning" in params) or "r1" in low or "think" in low,
                       "structured_output": ("response_format" in params
                                             or "structured_outputs" in params),
                       "created": m.get("created")})
    out = {"status": "MEASURED", "fetched_utc": _iso(t), "source": MODELS_URL,
           "families": sorted({m["family"] for m in models}),
           "models": sorted(models, key=lambda m: (-(m.get("created") or 0), m["id"]))}
    _save(path, out)
    return out


def model_rate(attrib: dict[str, Any], model: str) -> tuple[float, str]:
    """The seat's measured yield per call -- the same formula `lab_rate` applies to labs, so the
    auction ranks models and labs on one scale. Under three calls a seat is on PROBATION."""
    row = (attrib.get("by_model") or {}).get(model) or {}
    calls = int(row.get("calls") or 0)
    if calls < 3:
        return 1.0, "PROBATION"
    useful = (float(row.get("compiled") or 0) + 5.0 * float(row.get("passed") or 0)
              + 0.25 * float(row.get("requests") or 0))
    return (1.0 + useful) / (1.0 + calls), "MEASURED"


def plan_seats(tier: str, reg: dict[str, Any], attrib: dict[str, Any], *, pin: str = "",
               used: set[str] | None = None, coverage: bool = False, n: int = 3
               ) -> dict[str, Any]:
    """The ordered seats one job tries. Never a silent substitution: the plan names why each
    seat is where it is, and the job records the seat that actually answered.

    * COVERAGE slot (`coverage=True`, the first job of a cycle): the least-called free seat goes
      first, so every listed model keeps getting calls and a new one is measured, not ignored.
    * Otherwise seats rank by `model_rate` (probation = 1.0), deep jobs prefer reasoning seats,
      and a seat already used this cycle drops behind unused ones -- the load spreads over seats.
    * An unmeasured registry has no seats to plan with: a `:free` env pin is used as written; a
      paid pin never is."""
    if reg.get("status") not in ("MEASURED", "STALE"):
        if pin.endswith(":free"):
            return {"seats": [pin], "why": "registry UNMEASURED; :free env pin used as written"}
        return {"seats": [], "why": "registry UNMEASURED and no :free pin: MODEL_UNAVAILABLE"}
    u = used or set()
    calls = {k: int((v or {}).get("calls") or 0)
             for k, v in (attrib.get("by_model") or {}).items()}
    models = [m for m in reg["models"] if m.get("free")]
    if not models:
        return {"seats": [], "why": "no free model is listed: MODEL_UNAVAILABLE"}
    want_reasoning = tier == "deep"

    def key(m: dict[str, Any]) -> tuple[Any, ...]:
        rate, _ = model_rate(attrib, m["id"])
        return (m["id"] in u, bool(m.get("reasoning")) != want_reasoning, -rate,
                calls.get(m["id"], 0), m["id"])

    ranked = sorted(models, key=key)
    why = "ranked by measured seat yield"
    if coverage:
        cov = min(models, key=lambda m: (m["id"] in u, calls.get(m["id"], 0), m["id"]))
        ranked = [cov] + [m for m in ranked if m["id"] != cov["id"]]
        why = (f"coverage slot: {cov['id']} is the least-called free seat "
               f"({calls.get(cov['id'], 0)} calls)")
    seats = [m["id"] for m in ranked[:n]]
    listed = {m["id"] for m in models}
    if pin and pin in listed and pin not in seats:
        seats = [*seats[:n - 1], pin]
    return {"seats": seats, "why": why,
            "pin": (None if not pin else "listed" if pin in listed else "DELISTED")}


def _local_chat(user: str, system: str, model: str, base_url: str, timeout: float = 600.0
                ) -> tuple[str, str | None]:
    """A loopback OpenAI-compatible server (ollama, llama.cpp, vLLM). Refuses any non-loopback
    host: the local rung exists so nothing leaves the box."""
    host = urllib.parse.urlparse(base_url).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        return "", f"LOCAL_REFUSED: {host!r} is not loopback"
    body = json.dumps({"model": model, "messages": [{"role": "system", "content": system},
                                                    {"role": "user", "content": user}],
                       "temperature": 0.7}).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        from libs.ops import openrouter_guard  # loopback never bills; the guard still sees it
        openrouter_guard.check_request(req)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            doc = json.loads(r.read().decode("utf-8"))
        return str(doc["choices"][0]["message"]["content"]), None
    except Exception as exc:
        return "", f"LOCAL_FAILED: {type(exc).__name__}: {str(exc)[:200]}"


def local_seat(env: dict[str, str]) -> tuple[str, str]:
    """(base_url, model) of the loopback open-weight seat, any family. LLM_LAB_LOCAL_* first,
    the older DEEPSEEK_LOCAL_* names still honoured."""
    return (env.get("LLM_LAB_LOCAL_BASE_URL") or env.get("DEEPSEEK_LOCAL_BASE_URL") or "",
            env.get("LLM_LAB_LOCAL_MODEL") or env.get("DEEPSEEK_LOCAL_MODEL") or "")


def make_chat(env: dict[str, str], reg: dict[str, Any], attrib: dict[str, Any] | None = None
              ) -> Callable[..., dict[str, Any]]:
    """Free cloud seats of every family (ranked per job by `plan_seats`), then the loopback
    open-weight seat. Each failed seat is an attempt on the record; the seat that answered is the
    model the job is credited to."""
    from libs.ops import llm_seat

    att = attrib or {}
    used: set[str] = set()

    def chat(user: str, system: str, tier: str) -> dict[str, Any]:
        seat = ds.seat_state(env)
        attempts: list[dict[str, Any]] = []
        plan: dict[str, Any] = {"seats": [], "why": "DARK"}
        if seat.lit:
            pin = seat.deep_model if tier == "deep" else seat.bulk_model
            plan = plan_seats(tier, reg, att, pin=pin, used=used, coverage=not used)
            for mid in plan["seats"]:
                ls = llm_seat.Seat(name=f"llm_lab_{tier}",
                                   base_url=env.get("DEEPSEEK_BASE_URL",
                                                    "https://openrouter.ai/api/v1"),
                                   key=ds.resolve_key(env)[0], model=mid)
                text, err = llm_seat.chat(user, system=system, seat=ls,
                                          max_tokens=16000 if tier == "deep" else 6000)
                used.add(mid)
                if not err and text:
                    # llm_seat may swap a retired id for a listed one under us; credit the id
                    # that actually answered and keep the swap on the record.
                    resolved = getattr(llm_seat, "last_resolved", None)
                    actual = str(resolved(ls) or "") if callable(resolved) else ""
                    if actual and actual != mid:
                        attempts.append({"provider": "openrouter", "model": mid,
                                         "swapped_to": actual})
                        mid = actual
                    return {"text": text, "provider": "openrouter", "model": mid,
                            "family": model_family(mid), "pick": plan, "attempts": attempts}
                attempts.append({"provider": "openrouter", "model": mid,
                                 "error": str(err or "empty reply")[:300]})
            if not plan["seats"]:
                attempts.append({"provider": "openrouter", "error": plan["why"]})
        else:
            attempts.append({"provider": "openrouter", "error": "DARK"})
        lurl, lmodel = local_seat(env)
        if lurl and lmodel:
            text, err = _local_chat(user, system, lmodel, lurl)
            if not err:
                return {"text": text, "provider": "local", "model": f"local/{lmodel}",
                        "family": "local", "pick": plan, "attempts": attempts}
            attempts.append({"provider": "local", "model": f"local/{lmodel}", "error": err})
        return {"text": "", "error": "; ".join(str(a.get("error")) for a in attempts),
                "attempts": attempts}

    return chat


# ------------------------------------------------------------------------- feedback


def refresh_attribution(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Section 25. Join compiler receipts and gate verdicts back to the hypothesis that caused
    them, and credit lab / model / prompt version. Reads only; never feeds a held-out answer into
    a cold phase (the packet's blinding still strips outcomes before any prompt)."""
    t = now or _now_dt()
    memory = load_memory(root)
    by_hid = {m["hypothesis_id"]: m for m in memory}
    compiled: dict[str, list[dict[str, Any]]] = {}
    out_path = root / COMPILER_OUT
    try:
        text = out_path.read_text("utf-8") if out_path.stat().st_size < 400_000_000 else ""
    except OSError:
        text = ""
    compiler_status = "UNMEASURED: compiler output absent" if not text else "MEASURED"
    if "deepseek://" in text:
        try:
            doc = json.loads(text)
            rows = ((doc.get("hypotheses") or doc.get("candidates")) if isinstance(doc, dict)
                    else doc)
            for c in rows or []:
                url = str((c or {}).get("source_url") or "")
                if url.startswith("deepseek://"):
                    hid = url.rstrip("/").split("/")[-1]
                    if hid.startswith("dsc_"):
                        hid = url.split("/")[-2]
                    compiled.setdefault(hid, []).append(c)
        except ValueError:
            compiler_status = "UNMEASURED: compiler output unparseable"
    verdicts: dict[str, dict[str, Any]] = {}
    if compiled:
        try:
            from libs.research.hypothesis_graph import node_id_for_spec
            gid_to_hid = {}
            for hid, cands in compiled.items():
                for c in cands:
                    with_spec = {"symbol": c.get("symbol"), "family": c.get("family"),
                                 "params": c.get("params") or {}}
                    gid_to_hid[node_id_for_spec(with_spec)] = hid
            from collections import deque
            with (root / GATE_LEDGER).open(encoding="utf-8") as fh:
                for line in deque(fh, maxlen=GATE_TAIL):
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    vhid = gid_to_hid.get(str(r.get("graph_id") or ""))
                    if vhid:
                        v = verdicts.setdefault(vhid, {"judged": 0, "passed": 0, "gates": {}})
                        v["judged"] += 1
                        v["passed"] += int(bool(r.get("passed")))
                        g = str(r.get("terminal_gate") or "UNKNOWN")
                        v["gates"][g] = v["gates"].get(g, 0) + 1
        except (OSError, ImportError):
            pass
    calls = _load(root / ATTRIBUTION, {}).get("calls") or []
    by: dict[str, dict[str, dict[str, float]]] = {"by_lab": {}, "by_model": {}, "by_family": {},
                                                  "by_prompt": {}}

    def acc(kind: str, key: str, field: str, n: float = 1.0) -> None:
        row = by[kind].setdefault(key or "?", {})
        row[field] = row.get(field, 0) + n

    for c in calls:
        for kind, key in (("by_lab", c.get("lab")), ("by_model", c.get("model")),
                          ("by_family", model_family(str(c.get("model") or ""))),
                          ("by_prompt", c.get("prompt_version"))):
            acc(kind, str(key), "calls")
            acc(kind, str(key), "valid_json", 1.0 if c.get("schema") == "OK" else 0.0)
            for f in ("exact", "duplicate", "invalid", "data_request", "deepening"):
                acc(kind, str(key), f, float((c.get("counts") or {}).get(f, 0)))
            acc(kind, str(key), "requests", float(sum(
                (c.get("counts") or {}).get(f, 0) for f in ("data_request", "validation_attack",
                                                            "representation_request"))))
    for hid, m in by_hid.items():
        for kind, key in (("by_lab", m.get("lab")), ("by_model", m.get("model")),
                          ("by_family", model_family(str(m.get("model") or ""))),
                          ("by_prompt", m.get("prompt_version"))):
            if hid in compiled:
                acc(kind, str(key), "compiled")
            vd = verdicts.get(hid)
            if vd:
                acc(kind, str(key), "judged", vd["judged"])
                acc(kind, str(key), "passed", vd["passed"])
    doc = {"updated_utc": _iso(t), "calls": calls[-5000:], **by,
           "compiler": {"status": compiler_status, "hypotheses_compiled": len(compiled),
                        "candidates": sum(len(v) for v in compiled.values())},
           "gauntlet": {"status": ("MEASURED" if (root / GATE_LEDGER).exists()
                                   else "UNMEASURED: gate ledger absent"),
                        "hypotheses_judged": len(verdicts),
                        "hypotheses_passed": sum(1 for v in verdicts.values() if v["passed"]),
                        "verdicts": verdicts}}
    _save(root / ATTRIBUTION, doc)
    return doc


def record_call(root: Path, row: dict[str, Any]) -> None:
    doc = _load(root / ATTRIBUTION, {})
    if not isinstance(doc, dict):
        doc = {}
    doc.setdefault("calls", []).append(row)
    doc["calls"] = doc["calls"][-5000:]
    _save(root / ATTRIBUTION, doc)


# --------------------------------------------------------------------------- the cycle


def run_job(root: Path, job: dict[str, Any], packet: dict[str, Any], ctx: dict[str, Any],
            chat: Callable[..., dict[str, Any]], *, policy_hash: str) -> dict[str, Any]:
    lab = job["lab"]
    cold = ds.cold_context({"sections": packet.get("sections") or {},
                            "packet_hash": packet.get("packet_hash")})
    system, user = lab_prompt(lab, job, cold, ctx["contract"])
    tier = LABS[lab]["tier"]
    reply = chat(user, system, tier)
    if not reply.get("text"):
        fail_job(job, reply.get("error") or "empty reply")
        return {"job_id": job["job_id"], "lab": lab, "status": "CALL_FAILED",
                "why": reply.get("error"), "attempts": reply.get("attempts")}
    rid = f"lab{lab}_{job['job_id']}_{job.get('attempts', 0)}"
    sealed = ds.seal(rid, role=f"lab_{lab}", phase_a_output=reply["text"],
                     policy_hash=policy_hash, cold_context_hash=cold["cold_context_hash"],
                     provider=reply["provider"], model=reply["model"],
                     prompt_version=PROMPT_VERSION, root=root)
    objs, schema = parse_objects(reply["text"])
    prov = {"model": reply["model"], "provider": reply["provider"],
            "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
            "job_id": job["job_id"], "seal": sealed.get("path"),
            "packet_hash": packet.get("packet_hash")}
    recs = [validate(o, ctx) for o in objs]
    routed = route(root, recs, lab=lab, prov=prov, ctx=ctx, memory=ctx["memory"])
    job["status"], job["done_utc"] = "DONE", _iso(_now_dt())
    job["outcome"] = {"schema": schema, "objects": len(objs), **routed["counts"]}
    record_call(root, {"at": _iso(_now_dt()), "lab": lab, "job_id": job["job_id"],
                       "model": reply["model"], "provider": reply["provider"],
                       "prompt_version": PROMPT_VERSION, "schema": schema,
                       "objects": len(objs), "counts": routed["counts"],
                       "family": model_family(str(reply["model"])),
                       "seat_plan": (reply.get("pick") or {}).get("seats"),
                       "failed_seats": [a.get("model") for a in reply.get("attempts") or []]})
    return {"job_id": job["job_id"], "lab": lab, "status": "OK", "model": reply["model"],
            "provider": reply["provider"], "seal": sealed.get("verdict"), "schema": schema,
            "objects": len(objs), **routed}


def context(root: Path) -> dict[str, Any]:
    uni = universe(root)
    fams = family_specs(root)
    vocab = grammar_vocab()
    return {"universe": uni, "families": fams, "series": known_series(root, uni),
            "contract": contract_text(fams, vocab), "memory": load_memory(root)}


def calls_per_cycle(env: dict[str, str]) -> int:
    """Calls this cycle: the env knob, never more than a twentieth of today's remaining free
    requests (the OpenRouter free allowance is account-wide and other organs share it)."""
    try:
        k = int(env.get("DEEPSEEK_CALLS_PER_CYCLE", "4"))
    except ValueError:
        k = 4
    try:
        from libs.ops.llm_seat import free_budget_left, free_tier_only
        if free_tier_only():
            k = min(k, max(1, free_budget_left() // 20))
    except Exception:
        pass
    return max(0, k)


def cycle(root: Path | None = None, *, packet: dict[str, Any], policy_hash: str,
          env: dict[str, str] | None = None, chat: Callable[..., dict[str, Any]] | None = None,
          k: int | None = None, fetch: Callable[[str], Any] | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    """One pass: events + cadence -> queue -> score -> run k jobs -> drain debt -> feedback ->
    metrics. Never raises past a job: one bad job costs that job, not the cycle."""
    base = root or _ROOT
    e = dict(os.environ if env is None else env)
    t = now or _now_dt()
    q = load_queue(base)
    marks = _load(base / MARKS, {})
    if not isinstance(marks, dict):
        marks = {}
    rearmed = rearm_parked(q)
    made_events = scan_events(q, packet, marks, now=t)
    made_cadence = ensure_cadence(q, now=t)
    ctx = context(base)
    arrived = recheck_requests(base, ctx["series"], q)
    save_queue(base, q)
    _save(base / MARKS, marks)
    reg = refresh_models(base, fetch=fetch, now=t)
    attrib = _load(base / ATTRIBUTION, {})
    chat_fn = chat or make_chat(e, reg, attrib if isinstance(attrib, dict) else {})
    kk = calls_per_cycle(e) if k is None else k
    picked = select(due_jobs(q, now=t), attrib if isinstance(attrib, dict) else {}, kk, now=t)
    runs = []
    for job in picked:
        try:
            runs.append(run_job(base, job, packet, ctx, chat_fn, policy_hash=policy_hash))
        except Exception as exc:          # one bad job never takes the cycle down
            fail_job(job, f"{type(exc).__name__}: {exc}")
            runs.append({"job_id": job["job_id"], "lab": job["lab"], "status": "JOB_ERROR",
                         "why": f"{type(exc).__name__}: {str(exc)[:300]}"})
        save_queue(base, q)               # persisted after EVERY job: a kill loses one at most
    try:
        drain_limit = int(e.get("DEEPSEEK_DEBT_DRAIN", "25"))
    except ValueError:
        drain_limit = 25
    debt = drain_debt(base, drain_limit)
    fb = refresh_attribution(base, now=t)
    metrics = publish_metrics(base, q, fb, debt, reg, runs, now=t)
    return {"rearmed": rearmed, "events_enqueued": len(made_events),
            "cadence_enqueued": len(made_cadence), "requests_arrived": arrived,
            "calls_budget": kk, "runs": runs, "debt": debt, "metrics": metrics,
            "models": {"status": reg.get("status"),
                       "free_seats": len(reg.get("models") or []),
                       "families": reg.get("families") or []}}


def publish_metrics(root: Path, q: dict[str, Any], fb: dict[str, Any], debt: dict[str, Any],
                    reg: dict[str, Any], runs: list[dict[str, Any]], *,
                    now: datetime | None = None) -> dict[str, Any]:
    """Section 38. Every number is MEASURED from the lab's own files or says UNMEASURED."""
    t = now or _now_dt()
    jobs = list(q["jobs"].values())
    pending = [j for j in jobs if j.get("status") == "PENDING"]
    oldest = min((_parse(j.get("created_utc")) or t for j in pending), default=None)
    calls = fb.get("calls") or []
    day = [c for c in calls if (_parse(c.get("at")) or t) > t - timedelta(days=1)]
    ok = [c for c in day if c.get("schema") == "OK"]
    objs = sum(int(c.get("objects") or 0) for c in day)

    def tot(f: str) -> int:
        return sum(int((c.get("counts") or {}).get(f, 0)) for c in day)

    reqs = _requests(root)
    last_ok = max((c.get("at") for c in calls), default=None)
    m = {
        "updated_utc": _iso(t),
        "liveness": {"last_successful_call_utc": last_ok or "UNMEASURED: no call has succeeded",
                     "this_cycle_runs": len(runs),
                     "this_cycle_ok": sum(1 for r in runs if r.get("status") == "OK"),
                     "models_registry": reg.get("status", "UNMEASURED")},
        "queue": {"pending": len(pending),
                  "done": sum(1 for j in jobs if j.get("status") == "DONE"),
                  "parked": sum(1 for j in jobs if j.get("status") == "PARKED"),
                  "pending_by_lab": {lab: sum(1 for j in pending if j["lab"] == lab)
                                     for lab in LABS},
                  "oldest_pending_utc": _iso(oldest) if oldest else None},
        "production_24h": {"calls": len(day), "objects": objs, "exact": tot("exact"),
                           "deepening": tot("deepening"), "data_requests": tot("data_request"),
                           "validation_attacks": tot("validation_attack"),
                           "duplicates": tot("duplicate"), "invalid": tot("invalid")},
        "quality_24h": ({"valid_schema_rate": round(len(ok) / len(day), 3),
                         "exact_rate": round(tot("exact") / objs, 3) if objs else None,
                         "duplicate_rate": round(tot("duplicate") / objs, 3) if objs else None}
                        if day else "UNMEASURED: no call in 24h"),
        "pipeline": {"compiler": fb.get("compiler"), "gauntlet": {
            k: v for k, v in (fb.get("gauntlet") or {}).items() if k != "verdicts"}},
        "debt": {"coverage_owed": debt.get("owed"), "drained_this_cycle": debt.get("donated"),
                 "drain_cycles_at_this_rate": debt.get("drain_cycles_at_this_rate"),
                 "open_requests": len(reqs["open"]),
                 "open_by_type": {tt: sum(1 for r in reqs["open"].values()
                                          if r.get("object_type") == tt)
                                  for tt in ("DATA_REQUEST", "SOURCE_ACQUISITION_REQUEST",
                                             "REPRESENTATION_REQUEST", "VALIDATION_ATTACK")}},
        "economics": {"inference_cost_usd": 0.0 if os.environ.get("QUANT_FREE_TIER", "1") != "0"
                      else "UNMEASURED: paid route enabled",
                      "free_requests_used_24h": len(day)},
        "by_lab": fb.get("by_lab"), "by_model": fb.get("by_model"),
        "by_family": fb.get("by_family"),
        "authority": "RESEARCH GENERATION ONLY -- cannot promote, size, certify, arm or merge",
    }
    return m
