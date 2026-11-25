"""THE FREE-MODEL CONVERSION LANES -- free LLMs used to CONVERT what the desk already holds into
judge-testable cells, not only to generate more prose; every lane a job in one registry, every
job weighted by what it turned into certificates and live edges.

THE ASK (owner, 2026-11-25): "use the free models for conversion". Measured on the committed
state that day: 9,376 compiler rows carry a PROSE conditioner ("positioning", "event",
"seasonality", "macro", "carry", "microstructure", "cross_asset") that the replay refuses
(`family_spec.UNHONOURED_VARIANT`), and the sandbox federation's ~29.4k ideas were judged on the
family's DEFAULTS because their rule was prose. Neither needs a new idea; both need a translation
that invents nothing.

THE LANES (each one a job kind in `data/free_model_jobs.json`):

  translator         prose rows -> exact settings. The model may only (a) set a family keyword to
                     a number that appears VERBATIM in the row's own text, quoting the words, (b)
                     pick one `alt:` spec the catalog OFFERS (PIT thresholds only), or (c) pick a
                     modifier the replay honours that the row's own axis or words license. Every
                     proposal is re-validated here (`validate_translation`) and then through
                     `family_spec.translate` / `is_testable`; anything else is DROPPED and counted
                     by reason. A row whose text states `name=value` settings is translated
                     deterministically, with no model call at all.
  judge_feedback     per generator, a deterministic summary of what became of its rows: which
                     were not testable and why (family_spec), what they died of (producer_loop's
                     kill classes, aggregated -- never a held-out gate, a metric or a cell: Tier S
                     layer 4 blinds a generator to the held-out answer), and how many survived.
                     Written to reports/JUDGE_FEEDBACK.json; kimi_hunter and deepseek_cycle
                     append `feedback_block()` to their prompts. No model writes it.
  near_miss          cells the judge itself rosters as validity-pass, power-deficient
                     (forward_cure_route's FORWARD_CURE_ROSTER / POWER_CURE_CANDIDATES) that
                     failed EXACTLY ONE power gate get a few mutants from a FIXED structural menu
                     (one grid step of one setting, a session window, a volatility regime, one
                     catalog `alt:` conditioner) ordered by the failed gate's kill class
                     (producer_loop.kill_class / AXES_BY_KILL_CLASS discipline). No metric value
                     is ever read to choose a direction. Every mutant is stamped
                     `claim_family = lineage:nm:<root cell>` (the producer-loop lineage key, so
                     trial_ledger charges the whole lineage as one family-wise group and
                     grid_key keeps the strategy family), `breadth_unit` = the parent cell (a
                     variant is not a new bet), capped per parent per pass and per root for life.
                     The model only CHOOSES among menu ids; it cannot add one.
  redundancy_critic  deterministic: before a lane donates, its rows are checked against each
                     other and the compiler's rows by exact identity, by the hypothesis-family L1
                     rule (same family / symbol / chart / session / regime / categoricals --
                     thresholds collapse) and by the L2 family (the instrument replaced by its
                     measured correlation cluster, so one alt series + direction on co-moving
                     symbols is one bet). A lane's own duplicate is not donated; nothing already
                     on the docket is removed (hypothesis_families keeps and re-aims those, by
                     standing order). NO MODEL IS USED: a tie-break between two identical-rule
                     rows has no information a model could add, so the lane is deterministic.
  alt_generation     the alt-catalog slice kimi_hunter and deepseek_cycle already carry
                     (research/alt_catalog.py); registered so its yield and weight are scored
                     with the rest. Executed by those organs, not here.
  data_discovery     placeholder for the data-source discovery job (branch
                     claude/llm-data-discovery); registered, never executed here until wired.
  math_proposer      free models propose objects IN the math lab's grammar
                     (research/mathlab/llm_proposer.py); validated there (look-ahead, unknown
                     primitives, duplicates dropped by reason) and queued for the math_lab leg's
                     `math:llm_proposer` tradition, which charges, judges and donates them.

PROVIDER-AGNOSTIC. Every model call goes through `route_ask`: OpenRouter's free rotation
(libs/ops/openrouter_free) and then every lit cn_ensemble seat (Groq, SiliconFlow, hcnsec,
AgentRouter, yjs, Cloudflare and any box-file provider), with failover. A relay receives a prompt
only when `cn_ensemble.assert_public` passes on it, and only inside its own daily allowance.

THE REGISTRY IS DATA, NEVER CODE. A job is {name, kind, template, status, weight, added_by,
added_at}; `validate_job` refuses an unknown kind or template, a template of another kind, a bad
name or status -- arbitrary text is never executed. Each pass re-scores the weights from the
funnel's `by_lane` (certified + live per testable output, shrunk toward the pooled rate at small n
exactly as libs/research/live_yield.shrink does), two-sided in [WEIGHT_MIN, WEIGHT_MAX]; a job
that converted nothing over MIN_PARK_N testable outputs is PARKED at WEIGHT_MIN (never deleted)
and re-tested after RETEST_AFTER_DAYS; a job younger than EXPLORE_DAYS keeps at least par. The
pass's model calls are split across the LLM jobs in proportion to weight.

WHAT IT NEVER DOES. It moves no gate, DSR, FDR or trial count, writes no certificate, removes no
docket row, and never makes a number up. An unreadable input is UNMEASURED, never 0 (L1.28a).

    python desks/mt5/research/conversion_lanes.py --once [--budget-s 300] [--no-llm]
Clock: hourly leg `conversion_lanes` (research/hourly_cycle.py).
Artifacts: reports/CONVERSION_LANES.json, reports/JUDGE_FEEDBACK.json,
data/intelligence/conversion_<lane>/discoveries_*.json, data/conversion_lanes/ledger.json.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
SEAT = "conversion_lanes"
JOBS = DESK / "data" / "free_model_jobs.json"
STATE_DIR = DESK / "data" / "conversion_lanes"
LEDGER = STATE_DIR / "ledger.json"
TRANSLATE_QUEUE = STATE_DIR / "translate_queue.jsonl"
FEEDBACK_EXPOSURE = STATE_DIR / "feedback_exposure.json"
REPORT = DESK / "reports" / "CONVERSION_LANES.json"
FEEDBACK = DESK / "reports" / "JUDGE_FEEDBACK.json"
FUNNEL = DESK / "reports" / "FUNNEL.json"
COMPILER = DESK / "data" / "hypotheses" / "miner_candidates.json"
PRODUCER_LOOP = DESK / "reports" / "PRODUCER_LOOP.json"
JUDGE_REACH = DESK / "reports" / "JUDGE_REACH.json"
CURE_ROSTER = DESK / "reports" / "FORWARD_CURE_ROSTER.json"
CURE_SNAPSHOT = DESK / "reports" / "POWER_CURE_CANDIDATES.json"
INTEL = ROOT / "data" / "intelligence"
REGISTRY_DB = ROOT / "data" / "alpha_registry.sqlite"

# ------------------------------------------------------------------------------ the registry
#: The lane names E35 reads from FUNNEL.json `by_lane` (plus any registry-added job).
LANES = ("alt_generation", "data_discovery", "translator", "judge_feedback", "near_miss",
         "redundancy_critic", "math_proposer")
#: kind -> (executed here?, uses a model?)
KINDS: dict[str, tuple[bool, bool]] = {
    "translate": (True, True), "feedback": (True, False), "near_miss": (True, True),
    "critic": (True, False), "alt_generation": (False, True), "data_discovery": (False, True),
    "math_proposer": (True, True)}
#: template id -> its kind. A template is code in this module, never text from the registry.
TEMPLATES: dict[str, str] = {
    "translate_v1": "translate", "feedback_v1": "feedback", "near_miss_v1": "near_miss",
    "critic_v1": "critic", "alt_catalog_v1": "alt_generation",
    "data_discovery_v1": "data_discovery", "math_proposer_v1": "math_proposer"}
STATUSES = ("ACTIVE", "PARKED", "PLACEHOLDER")
_NAME = re.compile(r"[a-z][a-z0-9_]{2,47}")
WEIGHT_MIN, WEIGHT_MAX = 0.25, 4.0
#: Below this many testable outputs a job's yield is shrunk toward the pooled rate.
MIN_STAGE_N = 10
PRIOR_STRENGTH = 10.0
#: A job with this many testable outputs and nothing certified is PARKED (never deleted).
MIN_PARK_N = 200
RETEST_AFTER_DAYS = 30
#: A job younger than this keeps at least par weight (the exploration share for new jobs).
EXPLORE_DAYS = 14
#: Model calls one pass may spend across every LLM job, split by weight.
MAX_CALLS_PER_PASS = int(os.environ.get("CONVERSION_LANES_CALLS", "12"))
DEFAULT_BUDGET_S = 300.0

DEFAULT_JOBS: tuple[dict[str, Any], ...] = tuple(
    {"name": n, "kind": k, "template": t, "status": s, "weight": 1.0,
     "added_by": "claude:conversion-lanes", "added_at": "2026-11-25T00:00:00+00:00"}
    for n, k, t, s in (("alt_generation", "alt_generation", "alt_catalog_v1", "ACTIVE"),
                       ("data_discovery", "data_discovery", "data_discovery_v1", "PLACEHOLDER"),
                       ("translator", "translate", "translate_v1", "ACTIVE"),
                       ("judge_feedback", "feedback", "feedback_v1", "ACTIVE"),
                       ("near_miss", "near_miss", "near_miss_v1", "ACTIVE"),
                       ("redundancy_critic", "critic", "critic_v1", "ACTIVE"),
                       ("math_proposer", "math_proposer", "math_proposer_v1", "ACTIVE")))


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _parse(ts: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, default=str)
    os.replace(tmp, p)


def validate_job(entry: Any) -> tuple[dict[str, Any] | None, str]:
    """(the job, "") or (None, why it is refused). Unknown kinds and templates are refused."""
    if not isinstance(entry, dict):
        return None, "not an object"
    name = str(entry.get("name") or "")
    if not _NAME.fullmatch(name):
        return None, f"name {name[:40]!r} is not [a-z][a-z0-9_]{{2,47}}"
    kind, tpl = str(entry.get("kind") or ""), str(entry.get("template") or "")
    if kind not in KINDS:
        return None, f"{name}: unknown kind {kind[:40]!r}"
    if TEMPLATES.get(tpl) != kind:
        return None, f"{name}: template {tpl[:40]!r} is not a registered {kind} template"
    status = str(entry.get("status") or "ACTIVE")
    if status not in STATUSES:
        return None, f"{name}: status {status[:20]!r} not in {STATUSES}"
    try:
        w = float(entry.get("weight", 1.0))
    except (TypeError, ValueError):
        return None, f"{name}: weight is not a number"
    if w != w or w <= 0:
        return None, f"{name}: weight must be positive"
    if not str(entry.get("added_by") or "") or _parse(entry.get("added_at")) is None:
        return None, f"{name}: added_by / added_at (ISO time) are required"
    job = {"name": name, "kind": kind, "template": tpl, "status": status,
           "weight": round(min(WEIGHT_MAX, max(WEIGHT_MIN, w)), 4),
           "added_by": str(entry["added_by"])[:80], "added_at": str(entry["added_at"])}
    for k in ("parked_at", "retest_at", "baseline", "why"):
        if k in entry:
            job[k] = entry[k]
    return job, ""


def load_jobs(path: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """(valid jobs, refusals). An absent file is the DEFAULT_JOBS; every default lane is present
    even when the file omits it (a registry edit can add jobs, never lose a standing lane)."""
    doc = _read(path or JOBS)
    raw = doc.get("jobs") if isinstance(doc, dict) else None
    jobs: list[dict[str, Any]] = []
    refused: list[str] = []
    seen: set[str] = set()
    for e in (raw if isinstance(raw, list) else []):
        job, why = validate_job(e)
        if job is None:
            refused.append(why)
            continue
        if job["name"] in seen:
            refused.append(f"{job['name']}: duplicate name")
            continue
        seen.add(job["name"])
        jobs.append(job)
    for d in DEFAULT_JOBS:
        if d["name"] not in seen:
            jobs.append(dict(d))
    return jobs, refused


def _lane_yield(entry: Any) -> tuple[int | None, int | None, int | None]:
    """(testable, certified, live) from one FUNNEL by_lane entry; None where UNMEASURED."""
    if not isinstance(entry, dict):
        return None, None, None
    st = entry.get("stages") if isinstance(entry.get("stages"), dict) else entry

    def num(k: str) -> int | None:
        v = st.get(k)
        return int(v) if isinstance(v, int) and not isinstance(v, bool) else None
    return num("testable"), num("certified"), num("live")


def rescore(jobs: list[dict[str, Any]], by_lane: Mapping[str, Any] | None,
            now: datetime) -> list[dict[str, Any]]:
    """New weights / statuses from the funnel's by_lane. Yield per job = (certified + live) per
    testable output, shrunk toward the pooled rate at small n; weight = yield / pooled, clipped
    two-sided. Unmeasured -> par. Never deletes a job."""
    lanes = by_lane if isinstance(by_lane, Mapping) else {}
    ys = {j["name"]: _lane_yield(lanes.get(j["name"])) for j in jobs}
    k_tot = sum((c or 0) + (lv or 0) for t, c, lv in ys.values() if t is not None and c is not None)
    n_tot = sum(t for t, c, _lv in ys.values() if t is not None and c is not None)
    pooled = (k_tot / n_tot) if n_tot else None
    out: list[dict[str, Any]] = []
    for j in jobs:
        j = dict(j)
        if j["status"] == "PLACEHOLDER" or j["kind"] in ("feedback", "critic"):
            out.append(j)        # no yield of its own to score: par until it has one
            continue
        if j["status"] == "PARKED":
            rt = _parse(j.get("retest_at"))
            if rt is not None and now >= rt:
                j.update(status="ACTIVE", weight=1.0, why="re-test date reached")
                j.pop("parked_at", None)
                j.pop("retest_at", None)
                j["baseline"] = dict(zip(("testable", "certified", "live"), ys[j["name"]],
                                         strict=True))
            out.append(j)
            continue
        t, c, lv = ys[j["name"]]
        base = j.get("baseline") if isinstance(j.get("baseline"), dict) else {}
        if t is not None:
            t -= int(base.get("testable") or 0)
            c = None if c is None else c - int(base.get("certified") or 0)
            lv = None if lv is None else lv - int(base.get("live") or 0)
        if t is None or c is None or pooled is None or pooled <= 0 or t <= 0:
            w = 1.0
            why = "par: yield UNMEASURED or no pooled rate yet"
        else:
            k = c + (lv or 0)
            own = (k / t) if t >= MIN_STAGE_N else (k + PRIOR_STRENGTH * pooled) / (
                t + PRIOR_STRENGTH)
            w = min(WEIGHT_MAX, max(WEIGHT_MIN, own / pooled))
            why = f"yield {own:.4g} vs pooled {pooled:.4g} on {t} testable outputs"
            added0 = _parse(j.get("added_at"))
            young = added0 is not None and now - added0 < timedelta(days=EXPLORE_DAYS)
            if t >= MIN_PARK_N and k == 0 and not young:     # a new job is explored first
                j.update(status="PARKED", parked_at=_iso(now),
                         retest_at=_iso(now + timedelta(days=RETEST_AFTER_DAYS)))
                w = WEIGHT_MIN
                why = f"PARKED: 0 certified/live from {t} testable outputs"
        added = _parse(j.get("added_at"))
        if added is not None and now - added < timedelta(days=EXPLORE_DAYS) \
                and j["status"] == "ACTIVE":
            w = max(w, 1.0)
        j["weight"] = round(w, 4)
        j["why"] = why
        out.append(j)
    return out


def call_shares(jobs: list[dict[str, Any]], total: int = MAX_CALLS_PER_PASS) -> dict[str, int]:
    """Model calls per executable LLM job this pass, proportional to weight, at least 1 each."""
    llm = [j for j in jobs if KINDS[j["kind"]] == (True, True) and j["status"] != "PLACEHOLDER"]
    if not llm or total <= 0:
        return {}
    wsum = sum(float(j["weight"]) for j in llm)
    return {j["name"]: max(1, round(total * float(j["weight"]) / wsum)) for j in llm}


def write_jobs(jobs: list[dict[str, Any]], path: Path | None = None) -> None:
    """Merge the re-scored jobs into the file ON DISK (a writer that appended a job since we
    read it keeps its entry); only weight / status / parking fields of known names change."""
    p = path or JOBS
    doc = _read(p)
    raw = list(doc.get("jobs") or []) if isinstance(doc, dict) else []
    by = {j["name"]: j for j in jobs}
    names = set()
    for e in raw:
        if isinstance(e, dict) and e.get("name") in by:
            j = by[e["name"]]
            names.add(e["name"])
            for k in ("weight", "status", "why", "parked_at", "retest_at", "baseline"):
                if k in j:
                    e[k] = j[k]
                elif k in ("parked_at", "retest_at"):
                    e[k] = None
    raw += [dict(j) for j in jobs if j["name"] not in names]
    out = dict(doc) if isinstance(doc, dict) else {}
    out.update(schema=1, jobs=raw, kinds=sorted(KINDS), templates=dict(TEMPLATES),
               rule=("one entry per free-model job: name, kind, template, status, weight, "
                     "added_by, added_at. Kinds and templates are code in "
                     "research/conversion_lanes.py; an unknown one is refused, never run. "
                     "Weights are re-scored each pass from FUNNEL.json by_lane; a PARKED job "
                     "is kept and re-tested, never deleted."))
    _atomic(p, out)


# -------------------------------------------------------------------------------- the router
Asker = Callable[[str, str], tuple[str, str, str | None]]


def route_ask(system: str, user: str, *, organ: str = SEAT,
              max_tokens: int = 4000) -> tuple[str, str, str | None]:
    """(text, "provider/model", error). OpenRouter's free rotation first, then every lit
    cn_ensemble seat (relays only on a public prompt, inside their daily allowance)."""
    errors: list[str] = []
    try:
        from libs.ops import llm_seat
        left = llm_seat.lane_budget_left(organ)
    except Exception:
        left = None
    if left is None or left > 0:
        try:
            from libs.ops import openrouter_free as orf
            key, _src = orf.resolve_key()
            if key:
                models, _b = orf.free_models(key)
                st = orf.load_state()
                text, model, err = orf.complete(
                    [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    key=key, models=models, state=st, max_tokens=max_tokens)
                if text.strip() and not err:
                    return text, f"openrouter/{model}", None
                errors.append(f"openrouter: {err or 'empty'}"[:160])
        except Exception as exc:
            errors.append(f"openrouter: {type(exc).__name__}"[:160])
    try:
        from libs.ops import cn_ensemble as cn
        public = True
        try:
            cn.assert_public(system, user)
        except ValueError:
            public = False
        extra, overlay = cn.extra_providers(ROOT, os.environ)
        env = {**os.environ, **overlay}
        now = _now()
        for p in (*cn.PROVIDERS, *extra):
            if p.name == "openrouter" or (p.relay and not public):
                continue
            seat = cn.seat_for(p, env)
            if not seat.lit:
                continue
            cap = getattr(p, "daily_cap", None)
            if p.relay and cap and cn._relay_calls_today(ROOT, p.name, now) >= int(cap):
                continue
            for model in seat.models[:3]:
                text, err = cn._chat(seat, model, system, user)
                if p.relay:
                    with contextlib.suppress(Exception):
                        cn._append(ROOT / cn.RELAY_LEDGER,
                                   {"at": _iso(now), "provider": p.name, "model": model,
                                    "organ": organ, "ok": not err})
                if text and text.strip() and not err:
                    return text, f"{p.name}/{model}", None
                errors.append(f"{p.name}/{model}: {err or 'empty'}"[:160])
    except Exception as exc:
        errors.append(f"cn_ensemble: {type(exc).__name__}"[:160])
    return "", "", "; ".join(errors[-4:]) or "no free provider lit"


def _json_of(text: str) -> Any:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("\n") + 1:] if "\n" in t else t
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = t.find(opener), t.rfind(closer)
        if 0 <= i < j:
            with contextlib.suppress(ValueError):
                return json.loads(t[i:j + 1])
    return None


# ---------------------------------------------------------------------------- the translator
#: The prose axes the discovery compiler writes, and the honoured modifiers each LICENSES with no
#: number: a seasonal axis is the replay's calendar regimes, nothing else. Every other axis is an
#: alt-data axis: only an offered `alt:` spec translates it.
AXIS_MODIFIERS: dict[str, dict[str, tuple[str, ...]]] = {
    "seasonality": {"regime": ("month_end", "quarter_end")},
}
#: Words in a row's own text that license a modifier value.
MODIFIER_WORDS: dict[tuple[str, str], tuple[str, ...]] = {
    ("session", "asia"): ("asia", "tokyo", "sydney"),
    ("session", "london"): ("london", "european session"),
    ("session", "ny"): ("new york", "ny session", "us session"),
    ("regime", "month_end"): ("month end", "month-end", "end of month", "end of the month"),
    ("regime", "quarter_end"): ("quarter end", "quarter-end", "end of quarter"),
    ("regime", "high_vol"): ("high vol", "high-vol", "volatile regime", "high volatility"),
    ("regime", "low_vol"): ("low vol", "low-vol", "calm regime", "low volatility"),
    ("side_mode", "revert"): ("fade", "revert", "mean-revert", "mean revert"),
    ("entry_timing", "delayed"): ("delayed entry", "wait one bar", "next bar"),
}
TEXT_FIELDS = ("title", "source_title", "mechanism_note", "mechanism", "exact_rules", "rule",
               "text", "testable_claim", "hypothesis", "why")
MAX_TRANSLATIONS_PER_ROW = 2
TRANSLATE_BATCH = 10
MAX_SPECS_PER_ROW = 12
_NUM = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?![\d])")


def numbers_in(text: Any) -> set[float]:
    return {float(m) for m in _NUM.findall(str(text or ""))}


def _norm_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def row_text(row: Mapping[str, Any]) -> str:
    parts = [str(row.get(k)) for k in TEXT_FIELDS if isinstance(row.get(k), str) and row.get(k)]
    return " | ".join(dict.fromkeys(parts))


def _fs() -> Any:
    from research import family_spec as fs
    return fs


def _ident(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def prose_inputs(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Compiler rows whose `conditioner` is prose (not an `alt:` spec), one item per distinct
    (symbol, family, params, chart, session)."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        p = r.get("params")
        if not isinstance(p, dict) or "conditioner" not in p:
            continue
        cond = str(p.get("conditioner") or "")
        if cond.startswith("alt:"):
            continue
        sym, fam = str(r.get("symbol") or ""), str(r.get("family") or "")
        if not sym or not fam:
            continue
        ax = r.get("axis") if isinstance(r.get("axis"), dict) else {}
        chart = str(ax.get("chart") or p.get("timeframe") or "H1").upper()
        sess = str(ax.get("session") or p.get("session") or "all").lower()
        base = {k: v for k, v in p.items() if k != "conditioner"}
        iid = _ident("prose", sym, fam, base, cond, chart, sess)
        out.setdefault(iid, {"id": iid, "kind": "compiler_prose", "symbol": sym, "family": fam,
                             "params": base, "axis": cond.strip().lower(), "chart": chart,
                             "session": sess, "text": row_text(r),
                             "source": str(r.get("source") or ""), "producer": str(
                                 r.get("producer") or r.get("source") or "")})
    return list(out.values())


def queue_inputs(path: Path | None = None, limit: int = 20_000) -> list[dict[str, Any]]:
    """Rows sandbox_runner set aside as not executable (its translate queue)."""
    p = path or TRANSLATE_QUEUE
    out: dict[str, dict[str, Any]] = {}
    try:
        lines = p.read_text("utf-8").splitlines()[-limit:]
    except OSError:
        return []
    for ln in lines:
        with contextlib.suppress(ValueError):
            r = json.loads(ln)
            if not isinstance(r, dict):
                continue
            for sym in r.get("symbols") or []:
                iid = _ident("queue", sym, r.get("family"), r.get("params"), r.get("text"))
                out[iid] = {"id": iid, "kind": "sandbox_queue", "symbol": str(sym),
                            "family": str(r.get("family") or ""),
                            "params": dict(r.get("params") or {}), "axis": "",
                            "chart": "H1", "session": "all", "text": str(r.get("text") or ""),
                            "source": str(r.get("source_id") or ""),
                            "producer": str(r.get("source_id") or "")}
    return list(out.values())


def registry_inputs(db: Path | None = None, limit: int = 5_000) -> list[dict[str, Any]] | None:
    """Read-only: sandbox-generated registry candidates whose rule is prose. None when the
    registry is absent on this host."""
    path = db or REGISTRY_DB
    if not path.exists():
        return None
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        cur = con.execute(
            "SELECT family, symbol, params_json, exact_rules, generator FROM research_candidates "
            "WHERE generator LIKE 'sandbox:%' AND exact_rules IS NOT NULL AND exact_rules != '' "
            "ORDER BY seq DESC LIMIT ?", (int(limit),))
        rows = cur.fetchall()
        con.close()
    except Exception:
        return None
    fs = _fs()
    out: dict[str, dict[str, Any]] = {}
    for fam, sym, pj, rules, gen in rows:
        try:
            params = json.loads(pj or "{}")
        except ValueError:
            params = {}
        params = params if isinstance(params, dict) else {}
        if fs.is_testable(fs.to_executable(str(fam or ""), params, prose=str(rules))["status"]):
            continue
        iid = _ident("registry", sym, fam, params, rules)
        out[iid] = {"id": iid, "kind": "registry_sandbox", "symbol": str(sym or ""),
                    "family": str(fam or ""), "params": params, "axis": "", "chart": "H1",
                    "session": "all", "text": str(rules), "source": str(gen or ""),
                    "producer": str(gen or "")}
    return list(out.values())


def licence(item: Mapping[str, Any], specs: Iterable[str] = ()) -> dict[str, Any]:
    """What a translation of `item` may use: the numbers its text states, the modifiers its axis
    or words license, and the offered `alt:` specs."""
    text = str(item.get("text") or "")
    low = _norm_text(text)
    mods: dict[str, set[str]] = {}
    for key, vals in AXIS_MODIFIERS.get(str(item.get("axis") or ""), {}).items():
        mods.setdefault(key, set()).update(vals)
    for (key, val), words in MODIFIER_WORDS.items():
        if any(w in low for w in words):
            mods.setdefault(key, set()).add(val)
    own = item.get("params") if isinstance(item.get("params"), dict) else {}
    nums = numbers_in(text) | {float(v) for v in own.values()
                               if isinstance(v, int | float) and not isinstance(v, bool)}
    return {"numbers": nums, "modifiers": {k: sorted(v) for k, v in mods.items()},
            "specs": sorted(set(specs)), "text": text}


def _quote_ok(quote: Any, text: str, value: float) -> bool:
    q = _norm_text(quote)
    return bool(q) and q in _norm_text(text) and value in numbers_in(q)


def validate_translation(item: Mapping[str, Any], proposal: Mapping[str, Any],
                         lic: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """(the donation's call params, "") or (None, the named reason it was dropped).

    EVERY number must appear verbatim in the row's own text with a quote that contains it (or be
    the row's own value, or the family's default -- a no-op); a conditioner must be an offered
    spec; a modifier must be licensed; the result must be testable."""
    fs = _fs()
    fam = str(item.get("family") or "")
    if str(proposal.get("family") or fam) != fam:
        return None, "family_changed"
    sig = fs.signature(fam)
    if not sig:
        return None, "unregistered_family"
    params = proposal.get("params")
    if not isinstance(params, dict) or not params:
        return None, "no_params"
    ev = proposal.get("evidence") if isinstance(proposal.get("evidence"), dict) else {}
    own = item.get("params") if isinstance(item.get("params"), dict) else {}
    vocab_keys = {"session", "regime", "side_mode", "entry_timing", "selector"}
    clean: dict[str, Any] = {}
    for k, v in params.items():
        k = str(k)
        if k == "conditioner":
            if str(v) not in set(lic.get("specs") or ()):
                return None, "conditioner_not_offered"
            clean[k] = str(v)
        elif k in vocab_keys and k not in sig:
            allowed = (lic.get("modifiers") or {}).get(k) or []
            if str(v).lower() not in allowed:
                return None, f"modifier_not_licensed:{k}"
            clean[k] = str(v).lower()
        elif isinstance(v, bool) or not isinstance(v, int | float):
            if k in own and own[k] == v:
                clean[k] = v
                continue
            return None, f"non_numeric_setting:{k}"
        else:
            fv = float(v)
            stated = fv in lic.get("numbers", set()) and _quote_ok(ev.get(k),
                                                                     lic.get("text", ""), fv)
            if (k in own and own[k] == v) or (k in sig and sig[k] == v) or stated:
                clean[k] = v
            else:
                return None, "invented_number"
    merged = {**own, **clean}
    sess = str(item.get("session") or "all")
    if "session" not in merged:
        merged["session"] = sess
    chart = str(item.get("chart") or "H1").upper()
    if chart != "H1" and "timeframe" not in merged:
        merged["timeframe"] = chart
    got = fs.translate(fam, merged, prose=str(lic.get("text") or ""))
    if not fs.is_testable(got["status"]):
        return None, f"not_testable:{got['status']}"
    if got.get("unread"):
        return None, "unread_keys"
    return dict(got["call"]), ""


def deterministic_translation(item: Mapping[str, Any]) -> dict[str, Any] | None:
    """A proposal read straight off the row's own `name=value` text (family_spec.stated_numbers
    through ALIASES), or None. Evidence is the `name=value` span itself."""
    fs = _fs()
    fam = str(item.get("family") or "")
    stated = fs.stated_numbers(item.get("text"))
    sig = fs.signature(fam) or {}
    alias = fs.ALIASES.get(fam, {})
    params: dict[str, Any] = {}
    ev: dict[str, str] = {}
    text = str(item.get("text") or "")
    for name, val in stated.items():
        key = name if name in sig else alias.get(name, "")
        if key and key in sig and key not in params:
            params[key] = val
            m = re.search(rf"{re.escape(name)}\s*[=:(]\s*{re.escape(str(val))}", text, re.I)
            ev[key] = m.group(0) if m else f"{name}={val}"
    return {"params": params, "evidence": ev} if params else None


def offered_specs(item: Mapping[str, Any], cat: Mapping[str, Any] | None) -> list[str]:
    """Catalog specs a row may be conditioned on: series for its own instrument first, then the
    general series, bounded."""
    if not isinstance(cat, Mapping):
        return []
    sym = str(item.get("symbol") or "").upper()
    rows = [r for r in cat.get("series") or [] if r.get("specs")]
    mine = [r for r in rows if r.get("symbol") == sym]
    general = [r for r in rows if not r.get("symbol")]
    seed = int(hashlib.sha256(str(item.get("id")).encode()).hexdigest()[:8], 16)
    if general:
        k = seed % len(general)
        general = general[k:] + general[:k]
    out: list[str] = []
    for r in (*mine, *general):
        out += list(r["specs"])
        if len(out) >= MAX_SPECS_PER_ROW:
            break
    return out[:MAX_SPECS_PER_ROW]


TRANSLATE_SYSTEM = (
    "You translate short trading-rule descriptions into exact settings of a fixed rule library. "
    "Rules you must follow:\n"
    "1. A numeric setting is allowed ONLY when its number appears verbatim in the row's own text; "
    "give the exact words that state it under evidence.\n"
    "2. A conditioner is allowed ONLY as one spec copied exactly from the row's offered list.\n"
    "3. A modifier (session / regime / side_mode / entry_timing) is allowed ONLY from the row's "
    "offered modifiers.\n"
    "4. Never make up a number. If nothing in the row licenses a setting, skip it.\n"
    "Return ONLY JSON: {\"translations\": [{\"id\": \"...\", \"params\": {\"name\": value}, "
    "\"evidence\": {\"name\": \"verbatim words from the text\"}, \"why\": \"one line\"} | "
    "{\"id\": \"...\", \"skip\": \"reason\"}]}. At most two translations per id.")


def translate_prompt(batch: list[dict[str, Any]], lic: Mapping[str, Mapping[str, Any]]) -> str:
    fs = _fs()
    lines = ["ROWS:"]
    for it in batch:
        sig = fs.signature(it["family"]) or {}
        lines.append(json.dumps({
            "id": it["id"], "rule": it["family"], "instrument": it["symbol"],
            "axis": it.get("axis") or None,
            "settings_and_defaults": dict(list(sig.items())[:14]),
            "text": str(it.get("text") or "")[:600],
            "offered_modifiers": lic[it["id"]]["modifiers"],
            "offered_conditioners": lic[it["id"]]["specs"]}, default=str))
    return "\n".join(lines)


def parse_translations(text: str) -> dict[str, list[dict[str, Any]]]:
    doc = _json_of(text)
    rows = doc.get("translations") if isinstance(doc, dict) else doc
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("id") and isinstance(r.get("params"), dict):
            out.setdefault(str(r["id"]), []).append(r)
    return out


def translated_row(item: Mapping[str, Any], call: dict[str, Any], *, mode: str,
                   model: str = "") -> dict[str, Any]:
    """The donation row (the compiler's EXACT_RECIPE shape), tagged lane=translator."""
    return {"kind": "hypothesis", "family": item["family"], "symbols": [item["symbol"]],
            "params": call, "lane": "translator", "translated_from": item["id"],
            "translation_mode": mode, **({"model": model} if model else {}),
            "title": f"{item['family']} on {item['symbol']} (translated {item.get('kind')})"[:300],
            "mechanism": str(item.get("text") or "")[:600],
            "text": str(item.get("text") or "")[:600],
            **({"source_id": item["source"]} if str(item.get("source") or "")
               .startswith("sandbox:") else {})}


def run_translator(items: list[dict[str, Any]], *, done: set[str], cat: Mapping[str, Any] | None,
                   ask: Asker | None, calls: int, deadline: float) -> dict[str, Any]:
    """Translate pending items: deterministic first, then up to `calls` model batches."""
    dropped: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    pending = [it for it in items if it["id"] not in done]
    attempted: list[str] = []
    llm_q: list[dict[str, Any]] = []
    lic: dict[str, dict[str, Any]] = {}
    for it in pending:
        lic[it["id"]] = licence(it, offered_specs(it, cat))
        det = deterministic_translation(it)
        if det is not None:
            call, why = validate_translation(it, det, lic[it["id"]])
            attempted.append(it["id"])
            if call is not None:
                rows.append(translated_row(it, call, mode="deterministic"))
                continue
            dropped[why] += 1
        if lic[it["id"]]["specs"] or lic[it["id"]]["modifiers"] or lic[it["id"]]["numbers"]:
            llm_q.append(it)
        else:
            # NOT marked attempted: a series the catalog gains later licenses it next pass,
            # and re-reading the licence costs no model call.
            dropped["nothing_licensed"] += 1
    used, models = 0, Counter()
    errors: list[str] = []
    for i in range(0, len(llm_q), TRANSLATE_BATCH):
        if ask is None or used >= calls or time.monotonic() > deadline:
            break
        batch = llm_q[i:i + TRANSLATE_BATCH]
        text, model, err = ask(TRANSLATE_SYSTEM, translate_prompt(batch, lic))
        used += 1
        if err or not text:
            errors.append(str(err)[:160])
            continue
        models[model] += 1
        got = parse_translations(text)
        for it in batch:
            attempted.append(it["id"])
            props = got.get(it["id"]) or []
            if not props:
                dropped["model_skipped"] += 1
            seen_calls: set[str] = set()
            for prop in props[:MAX_TRANSLATIONS_PER_ROW]:
                call, why = validate_translation(it, prop, lic[it["id"]])
                if call is None:
                    dropped[why.split(":", 1)[0]] += 1
                    continue
                key = json.dumps(call, sort_keys=True, default=str)
                if key not in seen_calls:
                    seen_calls.add(key)
                    rows.append(translated_row(it, call, mode="llm", model=model))
    return {"inputs": len(items), "pending": len(pending), "attempted": attempted,
            "rows": rows, "dropped": dict(dropped), "calls": used, "models": dict(models),
            "errors": errors[-5:], "llm_queue": len(llm_q)}


# -------------------------------------------------------------------------- judge feedback ---
#: Generator seat -> the producer keys its rows are attributed under across the stores.
FEEDBACK_SEATS: dict[str, tuple[str, ...]] = {
    "kimi_hunt": ("kimi_k3_deep_forest", "kimi", "kimi_hunt", "kimi_hunter"),
    "deepseek": ("deepseek", "deepseek_cycle", "deepseek_lab"),
}
#: Kill class -> how it reads to a generator. Held-out gates are never named (Tier S layer 4).
KILL_WORDS = {
    "DEAD_DATA": "the rule never built or never fired (missing data, unbuildable settings)",
    "COSTS": "the edge did not pay the spread and swap",
    "EXOTIC_UNIVERSE": "the instrument is exotic / not tradable here",
    "NO_OOS_EDGE": "no edge survived the statistical screen",
    "DUPLICATE": "the cell already existed",
    "TOO_FEW_TRADES": "too few trades to rule on",
    "UNMAPPED": "an unclassified refusal",
}
ADVICE = {
    "DEAD_DATA": "name instruments the desk trades and settings the rule library reads",
    "COSTS": "prefer slower horizons and liquid instruments where the move pays the spread",
    "EXOTIC_UNIVERSE": "stay on FX majors/crosses, metals, indices, energy",
    "NO_OOS_EDGE": "state a forced-flow mechanism; avoid generic indicator grids",
    "DUPLICATE": "move to instruments, sessions or data series nobody has tested",
    "TOO_FEW_TRADES": "widen the condition or the horizon on economic grounds",
}
WASTE_WORDS = {
    "PROSE_ONLY": "the rule was prose only: state settings as name=value",
    "DEFAULTS_ONLY": "only the rule's defaults were given: state the settings that differ",
    "UNHONOURED_VARIANT": ("a conditioner the replay cannot apply (words like 'macro' or "
                           "'carry'): use an offered alt: spec instead"),
    "NO_SYMBOLS": "no instrument was named",
}


def _norm(name: Any) -> str:
    try:
        from research.funnel import who
        return who(name)
    except Exception:
        return re.sub(r"[^a-z0-9]+", "_", str(name or "").lower()).strip("_")


def feedback_summary(aliases: Iterable[str], *, loop: Any, reach: Any,
                     rows: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    """Aggregates only. Every input unreadable -> UNMEASURED with the reason."""
    keys = {_norm(a) for a in aliases}
    lp = next((r for r in (loop or {}).get("producers") or [] if isinstance(r, dict)
               and _norm(r.get("producer")) in keys), None) if isinstance(loop, dict) else None
    jr = next((r for r in (reach or {}).get("producers") or [] if isinstance(r, dict)
               and _norm(r.get("producer")) in keys), None) if isinstance(reach, dict) else None
    out: dict[str, Any] = {"producer_keys": sorted(keys)}
    if rows is not None:
        fs = _fs()
        q: Counter[str] = Counter()
        n = 0
        for r in rows:
            src = _norm(r.get("producer") or r.get("source"))
            if src not in keys:
                continue
            n += 1
            prose = str(r.get("exact_rules") or r.get("mechanism_note") or "")
            p = r.get("params") if isinstance(r.get("params"), dict) else {}
            q[str(fs.to_executable(str(r.get("family") or ""), p, prose=prose)["status"])] += 1
        out["compiled_rows"] = n
        out["testable_rows"] = sum(v for k, v in q.items() if k in fs.TESTABLE)
        out["not_testable"] = {k: v for k, v in q.items() if k in WASTE_WORDS}
    else:
        out["compiled_rows"] = UNMEASURED
    if lp is not None:
        hist = lp.get("kill_class_histogram")
        out["judged"] = lp.get("cells_judged") if isinstance(lp.get("cells_judged"), int) \
            else UNMEASURED
        out["died_of"] = ({k: int(v) for k, v in hist.items() if k in KILL_WORDS
                           and isinstance(v, int) and v} if isinstance(hist, dict) else UNMEASURED)
        out["survived"] = lp.get("certificates") if isinstance(lp.get("certificates"), int) \
            else UNMEASURED
    else:
        out.update(judged=UNMEASURED, died_of=UNMEASURED, survived=UNMEASURED)
    if jr is not None:
        out["reach"] = str(jr.get("verdict") or UNMEASURED)
    return out


def render_feedback(s: Mapping[str, Any]) -> str:
    """The prompt block: counts and fixed advice only, no cell, metric or held-out gate."""
    lines = ["WHAT BECAME OF YOUR EARLIER PROPOSALS (aggregate counts from this desk's records):"]
    n = s.get("compiled_rows")
    if isinstance(n, int) and n:
        lines.append(f"- {n} compiled rows, {s.get('testable_rows', 0)} carried an exact "
                     "testable rule.")
        for k, v in sorted((s.get("not_testable") or {}).items(), key=lambda kv: -kv[1])[:4]:
            lines.append(f"- {v} not testable: {WASTE_WORDS[k]}.")
    died = s.get("died_of")
    if isinstance(died, dict) and died:
        tot = sum(died.values())
        for k, v in sorted(died.items(), key=lambda kv: -kv[1])[:4]:
            lines.append(f"- {round(100 * v / tot)}% of judged cells: {KILL_WORDS[k]}.")
        top = max(died, key=lambda k: died[k])
        if top in ADVICE:
            lines.append(f"- So: {ADVICE[top]}.")
    if isinstance(s.get("survived"), int):
        lines.append(f"- {s['survived']} of your cells survived every test so far.")
    return "\n".join(lines) if len(lines) > 1 else ""


def build_feedback(*, rows: list[Mapping[str, Any]] | None, now: datetime,
                   loop_path: Path | None = None, reach_path: Path | None = None
                   ) -> dict[str, Any]:
    loop, reach = _read(loop_path or PRODUCER_LOOP), _read(reach_path or JUDGE_REACH)
    seats = {}
    for seat, aliases in FEEDBACK_SEATS.items():
        s = feedback_summary(aliases, loop=loop, reach=reach, rows=rows)
        seats[seat] = {"summary": s, "block": render_feedback(s)}
    return {"generated_utc": _iso(now), "organ": SEAT,
            "inputs": {"producer_loop": "READ" if isinstance(loop, dict) else UNMEASURED,
                       "judge_reach": "READ" if isinstance(reach, dict) else UNMEASURED,
                       "compiler": "READ" if rows is not None else UNMEASURED},
            "rule": ("deterministic aggregates per generator; no cell, metric or held-out gate "
                     "is named (Tier S layer 4); generators only read the block"),
            "seats": seats}


def feedback_block(seat: str, path: Path | None = None) -> str:
    """The block a generator appends to its prompt, "" when none is written. Records exposure."""
    doc = _read(path or FEEDBACK)
    blk = (((doc or {}).get("seats") or {}).get(seat) or {}).get("block") \
        if isinstance(doc, dict) else None
    if not blk:
        return ""
    with contextlib.suppress(Exception):      # its own file: a generator never races the pass
        exp = _read(FEEDBACK_EXPOSURE) or {}
        e = exp.setdefault(seat, {"shown": 0})
        e["shown"] = int(e.get("shown") or 0) + 1
        e["last"] = _iso(_now())
        _atomic(FEEDBACK_EXPOSURE, exp)
    return str(blk)


# --------------------------------------------------------------------------- near-miss ------
MAX_MUTANTS_PER_PARENT = 4
LIFETIME_MUTANTS_PER_ROOT = 8
MAX_PARENTS_PER_PASS = 25
MAX_DEPTH = 2
STEP_UP, STEP_DOWN = 1.25, 0.8
SESSIONS = ("asia", "london", "ny")
VOL_REGIMES = ("high_vol", "low_vol")
NM_PREFIX = "lineage:nm:"
#: The failed power gate's kill class -> the axes in preference order (producer_loop's
#: discipline: a structural axis per class, never a direction read off a metric).
NM_AXES: dict[str, tuple[str, ...]] = {
    "COSTS": ("session", "regime", "step_up", "alt"),
    "TOO_FEW_TRADES": ("step_down", "session", "alt"),
    "NO_OOS_EDGE": ("regime", "alt", "session", "step_up", "step_down"),
}
NM_DEFAULT_AXES = ("regime", "session", "alt", "step_up", "step_down")
NEVER_STEP = frozenset({"atr_n", "rr", "stop_atr", "ttl_bars"})


def near_miss_parents(roster: Any) -> list[dict[str, Any]]:
    """Rostered validity-pass rows that failed EXACTLY ONE power gate, with a shadow spec."""
    rows = roster.get("rows") or roster.get("candidates") if isinstance(roster, dict) else None
    out = []
    for key, r in sorted((rows or {}).items()) if isinstance(rows, dict) else []:
        if not isinstance(r, dict) or r.get("validity_pass") is not True:
            continue
        failed = r.get("failed_power_gates")
        spec = r.get("shadow_spec") if isinstance(r.get("shadow_spec"), dict) else {}
        if not (isinstance(failed, list) and len(failed) == 1 and spec.get("family")
                and spec.get("symbol")):
            continue
        out.append({"key": str(key), "cell": str(r.get("cell") or key), "failed": str(failed[0]),
                    "symbol": str(spec["symbol"]), "family": str(spec["family"]),
                    "params": dict(spec.get("params") or {}),
                    "lineage_root": r.get("lineage_root"), "depth": int(r.get("depth") or 0)})
    return out


def _kill(gate: str) -> str:
    try:
        from research.producer_loop import kill_class
        return kill_class(gate)
    except Exception:
        return "UNMAPPED"


def mutation_menu(parent: Mapping[str, Any], cat: Mapping[str, Any] | None
                  ) -> list[dict[str, Any]]:
    """The fixed, bounded menu of structural mutants of one parent, ordered by its failed gate's
    kill class. No metric is read."""
    fs = _fs()
    fam, p = str(parent["family"]), dict(parent.get("params") or {})
    sig = fs.signature(fam) or {}
    axes = NM_AXES.get(_kill(str(parent.get("failed"))), NM_DEFAULT_AXES)
    menu: list[dict[str, Any]] = []
    for ax in axes:
        if ax in ("step_up", "step_down"):
            for k in sorted(sig):
                if k in NEVER_STEP or isinstance(sig[k], bool) or not isinstance(sig[k],
                                                                                 int | float):
                    continue
                cur = p.get(k, sig[k])
                if not isinstance(cur, int | float) or isinstance(cur, bool) or not cur:
                    continue
                f = STEP_UP if ax == "step_up" else STEP_DOWN
                new: Any = cur * f
                new = max(1, round(new)) if isinstance(sig[k], int) else round(new, 6)
                if new != cur:
                    menu.append({"op": f"{ax}_{k}", "params": {**p, k: new}})
                    break                                  # one setting per direction
        elif ax == "session":
            if str(p.get("session") or "all").lower() in ("", "all"):
                menu += [{"op": f"session_{s}", "params": {**p, "session": s}}
                         for s in SESSIONS]
        elif ax == "regime":
            if "regime" not in sig and str(p.get("regime") or "").lower() in (
                    "", "unconditional", "all", "any"):
                menu += [{"op": f"regime_{g}", "params": {**p, "regime": g}}
                         for g in VOL_REGIMES]
        elif ax == "alt" and "conditioner" not in p:
            for s in offered_specs({"id": parent.get("cell"), "symbol": parent["symbol"]},
                                   cat)[:2]:
                menu.append({"op": "alt_conditioner", "params": {**p, "conditioner": s}})
    for i, m in enumerate(menu):
        m["id"] = f"m{i}"
    return menu


NEAR_MISS_SYSTEM = (
    "You pick, from a fixed menu, the variants of a trading rule most worth testing. The rule "
    "nearly qualified. Choose at most {n} menu ids whose change has an economic reason to help "
    "(who is forced to trade, and when). You cannot add or edit a variant. Return ONLY JSON: "
    "{{\"picks\": [{{\"id\": \"m0\", \"why\": \"one line\"}}]}}.")


def pick_mutants(parent: Mapping[str, Any], menu: list[dict[str, Any]], n: int,
                 ask: Asker | None) -> tuple[list[dict[str, Any]], str]:
    """(chosen menu items, model) -- the model chooses ids; anything else falls back to the
    menu's own order. A pick outside the menu is ignored."""
    if not menu or n <= 0:
        return [], ""
    if ask is not None:
        user = json.dumps({"rule": parent["family"], "instrument": parent["symbol"],
                           "fell_short_on": KILL_WORDS.get(_kill(str(parent["failed"])), ""),
                           "menu": [{"id": m["id"], "change": m["op"]} for m in menu]})
        text, model, err = ask(NEAR_MISS_SYSTEM.format(n=n), user)
        doc = _json_of(text) if not err else None
        picks = doc.get("picks") if isinstance(doc, dict) else None
        by = {m["id"]: m for m in menu}
        chosen = []
        for pk in picks if isinstance(picks, list) else []:
            mid = str(pk.get("id") if isinstance(pk, dict) else pk)
            if mid in by and by[mid] not in chosen:
                chosen.append({**by[mid], "why": str((pk or {}).get("why") or "")[:200]
                               if isinstance(pk, dict) else ""})
            if len(chosen) >= n:
                break
        if chosen:
            return chosen, model
    return menu[:n], ""


def run_near_miss(parents: list[dict[str, Any]], *, ledger: dict[str, Any],
                  cat: Mapping[str, Any] | None, ask: Asker | None, calls: int,
                  deadline: float) -> dict[str, Any]:
    """Mutants for up to MAX_PARENTS_PER_PASS parents, inside every cap. `ledger["roots"]`
    (root -> minted, ratcheted) and `ledger["mutants"]` (identity -> root) are updated."""
    fs = _fs()
    roots = ledger.setdefault("roots", {})
    seen = ledger.setdefault("mutants", {})
    cells = ledger.setdefault("cells", {})
    rows: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    used = 0
    for par in parents[:MAX_PARENTS_PER_PASS]:
        if time.monotonic() > deadline:
            skipped["budget"] += 1
            continue
        mine = cells.get(par["cell"]) if isinstance(cells.get(par["cell"]), dict) else {}
        root = str(par.get("lineage_root") or mine.get("root") or par["cell"])
        depth = int(par.get("depth") or mine.get("depth") or 0)
        if depth >= MAX_DEPTH:
            skipped["max_depth"] += 1
            continue
        left = LIFETIME_MUTANTS_PER_ROOT - int(roots.get(root) or 0)
        if left <= 0:
            skipped["lifetime_cap"] += 1
            continue
        menu = mutation_menu(par, cat)
        n = min(MAX_MUTANTS_PER_PARENT, left)
        chosen, model = pick_mutants(par, menu, n, ask if used < calls else None)
        if ask is not None and used < calls and menu:
            used += 1
        for m in chosen:
            mp = dict(m["params"])
            mp.setdefault("session", "all")               # no fan-out: one mutant, one cell
            tf = par["cell"].split(".", 1)[0].split("@", 1)[1] if "@" in \
                par["cell"].split(".", 1)[0] else ""
            if tf and tf.upper() != "H1":
                mp.setdefault("timeframe", tf.upper())
            got = fs.translate(par["family"], mp)
            if not fs.is_testable(got["status"]):
                skipped[f"not_testable:{got['status']}"] += 1
                continue
            ident = _ident(par["symbol"], par["family"], got["call"])
            if ident in seen:
                skipped["already_minted"] += 1
                continue
            seen[ident] = root
            roots[root] = int(roots.get(root) or 0) + 1
            with contextlib.suppress(Exception):
                from research import alt_catalog as ac
                cid = ac._cell({"symbol": par["symbol"], "family": par["family"],
                                "params": got["call"]})
                if cid:
                    cells[cid] = {"root": root, "depth": depth + 1}
            rows.append({"kind": "hypothesis", "family": par["family"],
                         "symbols": [par["symbol"]], "params": got["call"], "lane": "near_miss",
                         "claim_family": f"{NM_PREFIX}{root}", "lineage_root": root,
                         "breadth_unit": f"cell:{root}", "mutation_of": par["cell"],
                         "operator": m["op"], "depth": depth + 1,
                         **({"model": model} if model else {}),
                         "title": f"{par['family']} on {par['symbol']}: {m['op']} of a "
                                  f"near-miss"[:300],
                         "mechanism": (m.get("why") or f"bounded {m['op']} mutant of a rule "
                                       f"that cleared every validity test")[:600]})
    return {"parents": len(parents), "rows": rows, "skipped": dict(skipped), "calls": used}


# --------------------------------------------------------------------- the redundancy critic --
def critic(rows: list[dict[str, Any]], existing: Iterable[Mapping[str, Any]] = (), *,
           clusters: Mapping[str, str] | None = None) -> tuple[list[dict[str, Any]],
                                                                dict[str, int]]:
    """Drop a lane row that duplicates another lane row or an existing compiler row: exact
    identity, same L1 rule, or same L2 family (correlation cluster). Deterministic; no model."""
    try:
        from research import hypothesis_families as hf
    except Exception:
        hf = None

    def norm(r: Mapping[str, Any]) -> dict[str, Any]:
        sym = r.get("symbol") or ((r.get("symbols") or [""])[0])
        return {"symbol": str(sym), "family": str(r.get("family") or ""),
                "params": dict(r.get("params") or {})}

    def keys(r: Mapping[str, Any]) -> tuple[str, str, str]:
        n = norm(r)
        exact = _ident(n["symbol"], n["family"], n["params"])
        if hf is None:
            return exact, exact, exact
        rule = hf.rule_key(n)
        return exact, rule, hf.family_key(n, clusters or {}, rule)

    held: dict[str, set[str]] = {"exact": set(), "rule": set(), "family": set()}
    for r in existing:
        e, ru, fa = keys(r)
        held["exact"].add(e)
        held["rule"].add(ru)
        held["family"].add(fa)
    kept: list[dict[str, Any]] = []
    why: Counter[str] = Counter()
    for r in rows:
        e, ru, fa = keys(r)
        hit = ("EXACT" if e in held["exact"] else "NEAR_RULE" if ru in held["rule"]
               else "SAME_FAMILY_CLUSTER" if fa in held["family"] else None)
        # A near-miss mutant is a variant BY DESIGN (same rule, one threshold stepped): it is
        # charged to its lineage and keeps the parent's breadth unit, so only an EXACT twin is
        # redundant for it; the rule/family tests apply to every other lane's rows.
        if hit and not (r.get("lane") == "near_miss" and hit != "EXACT"):
            why[hit] += 1
            continue
        held["exact"].add(e)
        held["rule"].add(ru)
        held["family"].add(fa)
        kept.append(r)
    return kept, {"in": len(rows), "kept": len(kept), **dict(why)}


# ---------------------------------------------------------------------------- donation -------
def donate(lane: str, rows: list[dict[str, Any]], now: datetime,
           root: Path | None = None) -> Path | None:
    if not rows:
        return None
    d = (root or INTEL) / f"conversion_{lane}"
    d.mkdir(parents=True, exist_ok=True)
    src = f"conversion_{lane}"
    out = []
    for r in rows:
        row = {**r, "source": src, "date": now.date().isoformat(),
               "url": f"conversion://{lane}/" + _ident(r.get("family"), r.get("symbols"),
                                                         r.get("params")),
               "available_time": _iso(now), "retrieved_at": _iso(now)}
        with contextlib.suppress(Exception):
            from libs.research.source_provenance import stamp_row
            stamp_row(row, ground=src, retrieved_at=_iso(now))
        out.append(row)
    p = d / f"discoveries_{now.strftime('%Y%m%d_%H%M%S')}.json"
    _atomic(p, {"source": src, "generated_at": _iso(now), "discoveries": out})
    return p


# ---------------------------------------------------------------------------- the pass -------
def _compiler_rows(path: Path, deadline: float) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        from research.funnel import iter_list
        return list(iter_list(path, "hypotheses", deadline=deadline))
    except Exception:
        d = _read(path)
        rows = d.get("hypotheses") if isinstance(d, dict) else None
        return rows if isinstance(rows, list) else None


def _catalog() -> Mapping[str, Any] | None:
    try:
        from research import alt_catalog as ac
        return ac.catalog()
    except Exception:
        return None


def run_pass(*, now: datetime | None = None, budget_s: float = DEFAULT_BUDGET_S,
             ask: Asker | None = None, use_llm: bool = True, write: bool = True,
             jobs_path: Path | None = None, compiler: Path | None = None,
             roster: Path | None = None, funnel: Path | None = None,
             intel_root: Path | None = None, ledger_path: Path | None = None,
             report_path: Path | None = None, feedback_path: Path | None = None,
             cat: Mapping[str, Any] | None = None,
             registry_db: Path | None = None) -> dict[str, Any]:
    now = now or _now()
    t0 = time.monotonic()
    deadline = t0 + budget_s * 0.85
    jobs, refused = load_jobs(jobs_path)
    fdoc = _read(funnel or FUNNEL)
    jobs = rescore(jobs, (fdoc or {}).get("by_lane") if isinstance(fdoc, dict) else None, now)
    shares = call_shares(jobs)
    asker: Asker | None = ask
    if asker is None and use_llm:
        def asker(system: str, user: str) -> tuple[str, str, str | None]:
            return route_ask(system, user)
    lpath = ledger_path or LEDGER
    ledger = _read(lpath) if isinstance(_read(lpath), dict) else {}
    lanes_led = ledger.setdefault("lanes", {})
    rows = _compiler_rows(compiler or COMPILER, deadline)
    cat = cat if cat is not None else _catalog()
    report: dict[str, Any] = {"generated_utc": _iso(now), "organ": SEAT, "refused_jobs": refused,
                              "jobs": jobs, "call_shares": shares, "lanes": {}}
    active = {j["name"]: j for j in jobs if j["status"] == "ACTIVE"}
    donated: list[dict[str, Any]] = []

    def tally(lane: str, **kw: int) -> None:
        e = lanes_led.setdefault(lane, {})
        for k, v in kw.items():
            e[k] = int(e.get(k) or 0) + int(v)

    if "judge_feedback" in active:
        fb = build_feedback(rows=rows, now=now)
        if write:
            _atomic(feedback_path or FEEDBACK, fb)
        n_blocks = sum(1 for s in fb["seats"].values() if s["block"])
        tally("judge_feedback", inputs=len(fb["seats"]), outputs=n_blocks)
        report["lanes"]["judge_feedback"] = {"seats": {k: v["summary"]
                                                       for k, v in fb["seats"].items()},
                                             "blocks_written": n_blocks}
    tr_rows: list[dict[str, Any]] = []
    if "translator" in active:
        items = prose_inputs(rows or []) + queue_inputs()
        reg = registry_inputs(registry_db)
        items += reg or []
        done = set(ledger.setdefault("translated", []))
        tr = run_translator(items, done=done, cat=cat,
                            ask=asker if use_llm else None,
                            calls=shares.get("translator", 0), deadline=deadline)
        ledger["translated"] = sorted(done | set(tr["attempted"]))
        tr_rows = tr.pop("rows")
        tr.pop("attempted")
        tr["registry"] = "READ" if reg is not None else f"{UNMEASURED}: no registry on host"
        tr["by_input"] = dict(Counter(i["kind"] for i in items))
        tr["lake"] = (cat or {}).get("status", UNMEASURED) if isinstance(cat, Mapping) \
            else UNMEASURED
        report["lanes"]["translator"] = tr
        tally("translator", inputs=tr["pending"], proposals=len(tr_rows),
              dropped=sum(tr["dropped"].values()))
    nm_rows: list[dict[str, Any]] = []
    if "near_miss" in active:
        rdoc = _read(roster or CURE_ROSTER) or _read(CURE_SNAPSHOT)
        parents = near_miss_parents(rdoc) if rdoc is not None else []
        nm = run_near_miss(parents, ledger=ledger.setdefault("near_miss", {}), cat=cat,
                           ask=asker if use_llm else None, calls=shares.get("near_miss", 0),
                           deadline=deadline)
        nm_rows = nm.pop("rows")
        nm["roster"] = "READ" if rdoc is not None else f"{UNMEASURED}: no cure roster"
        report["lanes"]["near_miss"] = nm
        tally("near_miss", inputs=len(parents), proposals=len(nm_rows))
    crit = {"status": "SKIPPED (job not ACTIVE)"}
    if "redundancy_critic" in active:
        clusters: dict[str, str] = {}
        with contextlib.suppress(Exception):
            from research import hypothesis_families as hf
            clusters = dict(hf.load_clusters(refresh=False)[0] or {})
        tr_rows, c1 = critic(tr_rows, rows or [], clusters=clusters)
        nm_rows, c2 = critic(nm_rows, rows or [], clusters=clusters)
        crit = {"translator": c1, "near_miss": c2, "model": "none (deterministic by design)"}
        tally("redundancy_critic", inputs=c1["in"] + c2["in"],
              outputs=c1["kept"] + c2["kept"])
    report["lanes"]["redundancy_critic"] = crit
    if "math_proposer" in active:      # free models propose objects IN the math lab's grammar
        from research.mathlab import llm_proposer as mp
        mpr = mp.run_job(ask=asker if use_llm else None, calls=shares.get("math_proposer", 0),
                         deadline=deadline, now=now, queue=lpath.parent / mp.QUEUE.name,
                         cat=cat, write=write)
        report["lanes"]["math_proposer"] = mpr
        tally("math_proposer", inputs=mpr["calls"], proposals=mpr["proposed"],
              dropped=sum(mpr["dropped"].values()), outputs=mpr["accepted"])
    for lane, rr in (("translator", tr_rows), ("near_miss", nm_rows)):
        if write and rr:
            p = donate(lane, rr, now, intel_root)
            report["lanes"].setdefault(lane, {})["donated_to"] = str(p)
        tally(lane, outputs=len(rr))
        donated += rr
    report["ledger"] = dict(lanes_led.items())
    report["donated"] = len(donated)
    report["summary"] = {"donated": len(donated), "translated": len(tr_rows),
                         "near_miss_mutants": len(nm_rows),
                         "refused_jobs": len(refused)}
    report["elapsed_s"] = round(time.monotonic() - t0, 2)
    if write:
        _atomic(lpath, ledger)
        _atomic(report_path or REPORT, report)
        write_jobs(jobs, jobs_path)
    return report


# ------------------------------------------------------------------------ the funnel's view ---
def lane_of(row: Mapping[str, Any]) -> str | None:
    lane = row.get("lane")
    if isinstance(lane, str) and lane:
        return lane
    p = row.get("params")
    if isinstance(p, dict) and str(p.get("conditioner") or "").startswith("alt:") and \
            str(row.get("source") or "") .startswith(("miner:kimi", "miner:deepseek")):
        return "alt_generation"
    if row.get("alt_catalog_organ"):
        return "alt_generation"
    return None


def by_lane(rows: list[Mapping[str, Any]] | None, *, seen: set[str] | None,
            certified: set[str] | None, live: set[str] | None,
            jobs: list[dict[str, Any]] | None = None, ledger: Any = None,
            cell_of: Callable[[Mapping[str, Any]], str | None] | None = None
            ) -> dict[str, dict[str, Any]]:
    """FUNNEL.json `by_lane`: per job, inputs -> outputs -> testable -> judged -> certified ->
    live and its registry weight. A stage whose input is unreadable is UNMEASURED, never 0."""
    jobs = jobs if jobs is not None else load_jobs()[0]
    led = (ledger or {}).get("lanes") if isinstance(ledger, dict) else None
    fs = _fs()
    if cell_of is None:
        from research import alt_catalog as ac
        cell_of = ac._cell
    out: dict[str, dict[str, Any]] = {}
    for j in jobs:
        e = (led or {}).get(j["name"]) if isinstance(led, dict) else None
        out[j["name"]] = {
            "weight": float(j["weight"]), "status": j["status"], "kind": j["kind"],
            "inputs": int(e.get("inputs") or 0) if isinstance(e, dict) else UNMEASURED,
            "outputs": int(e.get("outputs") or 0) if isinstance(e, dict) else UNMEASURED,
            "testable": 0 if rows is not None else UNMEASURED,
            "judged": 0 if rows is not None and seen is not None else UNMEASURED,
            "certified": 0 if rows is not None and certified is not None else UNMEASURED,
            "live": 0 if rows is not None and live is not None else UNMEASURED}
    if rows is not None:
        for r in rows:
            lane = lane_of(r)
            if lane not in out:
                continue
            e = out[lane]
            if lane == "alt_generation" and isinstance(e["outputs"], str):
                e["outputs"] = 0
            if lane == "alt_generation":
                e["outputs"] += 1
            p = r.get("params") if isinstance(r.get("params"), dict) else {}
            if not fs.is_testable(fs.to_executable(str(r.get("family") or ""), p)["status"]):
                continue
            e["testable"] += 1
            cid = cell_of(r)
            if not cid:
                continue
            ids = {cid, f"external.{cid}"}
            if seen is not None and ids & seen:
                e["judged"] += 1
            if certified is not None and ids & certified:
                e["certified"] += 1
            if live is not None and ids & live:
                e["live"] += 1
    for name, e in out.items():
        if name == "judge_feedback":
            e["testable"] = e["judged"] = e["certified"] = e["live"] = UNMEASURED
            e["why"] = ("its yield is the generators' own (attributed through kimi_hunt / "
                        "deepseek in by-producer)")
        elif name == "redundancy_critic":
            e["testable"] = e["judged"] = e["certified"] = e["live"] = UNMEASURED
            e["why"] = "a filter on the other lanes' rows: outputs are rows kept"
        elif e["kind"] == "data_discovery" and e["status"] == "PLACEHOLDER":
            for k in ("inputs", "outputs", "testable", "judged", "certified", "live"):
                e[k] = UNMEASURED
            e["why"] = "placeholder until branch claude/llm-data-discovery merges"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=float(
        os.environ.get("QUANT_LEG_BUDGET_S") or DEFAULT_BUDGET_S))
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run_pass(budget_s=a.budget_s, use_llm=not a.no_llm, write=not a.dry_run)
    tr = rep["lanes"].get("translator") or {}
    nm = rep["lanes"].get("near_miss") or {}
    print(f"conversion lanes: translator pending {tr.get('pending')} calls {tr.get('calls')} "
          f"dropped {tr.get('dropped')}; near-miss parents {nm.get('parents')}; donated "
          f"{rep['donated']}; refused jobs {len(rep['refused_jobs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
