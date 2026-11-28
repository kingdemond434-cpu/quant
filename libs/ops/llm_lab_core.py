"""LLM LAB CORE -- the shared ground of the 24/7 LLM research lab (`deepseek_lab`): the lab
catalogue (A-Q + conversion), state paths, the desk vocabulary a model may name, and output
contract ds-2.

THE CONTRACT. Exact rules, a falsifier, data inputs, a registered family + params (the `formula`
family takes an `alpha_grammar` expression, which is how a new mechanism becomes an exact
executable). Vague rules, unknown series, unregistered families and invalid expressions are named
and downgraded, never repaired by invention. Banal indicator variants are rejected as discoveries.

AUTHORITY. Research generation only; model text is data, never instruction.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import re
import sys
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


def context(root: Path) -> dict[str, Any]:
    uni = universe(root)
    fams = family_specs(root)
    vocab = grammar_vocab()
    return {"universe": uni, "families": fams, "series": known_series(root, uni),
            "contract": contract_text(fams, vocab), "memory": load_memory(root)}
