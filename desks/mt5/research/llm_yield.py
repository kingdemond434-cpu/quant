"""LLM_YIELD: what every model and generator turned its calls into, hourly, to the cert.

WHY (principal, hourly pass item 26, 2026-10-29: "every pass checks LLM lab and OpenRouter yield,
liveness with no silent success, conversion at each stage and real ROI per model and seat ... and
pushes the weak parts to max"; IDEA_QUEUE row 251). The desk could say which PRODUCERS wrote rows
(PRODUCER_YIELD) and which producers' cells certified (certificate_provenance), but not what a
given model id did with its calls: whether it answered, answered empty, proposed anything, and
whether any of that reached a cell, a verdict or a certificate. A seat that returns 200 with no
content reads as healthy everywhere else; this report is where it reads as what it is.

ONE REPORT, READ FROM THE ARTIFACTS THAT OWN EACH STAGE -- nothing here re-derives a verdict:

    calls / ok / empty    data/llm_spend.jsonl (llm_seat._record_spend: organ, model, tokens,
                          empty_content) -- one row per PARSED reply
    panel calls/failures  data/free_panel_state.json (lifetime counters, no timestamps)
    lab funnel            data/deepseek_lab/attribution.json by_model: calls, compiled, judged,
                          passed (the third-brain lab's own join to the verdict ledger)
    proposals             proposer-seat queue provenance and intelligence rows that carry a model
    generators            PRODUCER_YIELD (verdict, rows, declared replacement), the compiler's
                          per-source candidates, the moat registry's generator_yield table
                          (generated, donated, judged, survivors -- math lab traditions appear as
                          `math:<tradition>`), and certificate_provenance's certs by producer

WHAT IS NOT YET MEASURABLE IS SAID, NOT ZEROED (L1.28a). A failed call writes no spend row, and no
row after the first hop carries the model id, so a model's cells and certificates are reported
only where a lab joins them itself (the attribution feed). Every block names its source and is
UNMEASURED when that source is absent.

TWO RED CHECKS (exit 1), because a report nobody fails on is a report nobody reads:
  * SILENT SUCCESS -- an (organ, model) whose last `SILENT_RUNS` parsed replies were all empty.
  * A DEAD PRODUCER'S REPLACEMENT THAT IS ITSELF DEAD -- PRODUCER_YIELD lets a dead producer
    declare what replaced it; a replacement that also wrote nothing replaces nothing.

THE BUDGET FOLLOWS CONVERSION. `desks/mt5/data/llm_model_priority.json` gives each model a weight:
higher for models whose calls compile and pass, lower for models answering empty, zero for ids the
provider has retired. `libs.research.free_panel.available` spreads calls by calls/weight, so a
model that converts is asked proportionally more often and a model that does not is still asked,
just less -- the exploration that lets a weak model's weight recover. Free models only; the
gauntlet still judges every proposal.

    python llm_yield.py [--window-days 7] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SPEND = REPO / "data" / "llm_spend.jsonl"
PANEL = REPO / "data" / "free_panel_state.json"
LAB_ATTRIBUTION = REPO / "data" / "deepseek_lab" / "attribution.json"
SEAT_QUEUES = BASE / "data" / "proposer_seat"
INTEL_ROOTS = (BASE / "data" / "intelligence", REPO / "data" / "intelligence")
PRODUCER_YIELD = BASE / "reports" / "PRODUCER_YIELD.json"
MINER_CANDIDATES = BASE / "data" / "hypotheses" / "miner_candidates.json"
REGISTRY = REPO / "data" / "alpha_registry.sqlite"
CERT_PROVENANCE = BASE / "data" / "certificate_provenance.json"
REPORT = BASE / "reports" / "LLM_YIELD.json"
LAB_REPORTS = {"mathlab": BASE / "reports" / "MATH_LAB.json",
               "physics_lab": BASE / "reports" / "PHYSICS_LAB.json",
               "world_lab": BASE / "reports" / "WORLD_LAB.json"}
#: A lab report older than this is a clock that stopped (the labs run hourly).
LAB_STALE_H = 6.0
PRIORITY = BASE / "data" / "llm_model_priority.json"

UNMEASURED = "UNMEASURED"
WINDOW_DAYS = 7
#: "Success with zero output for more than 2 runs" (item 26): three empty replies in a row.
SILENT_RUNS = 3
#: Calls a model needs before its conversion moves its weight; under this it keeps weight 1.0.
MIN_CALLS_FOR_WEIGHT = 5
#: ROI = (compiled + PASS_WEIGHT * passed) / calls -- the lab's own seat score, kept identical.
PASS_WEIGHT = 5.0
SILENT_WEIGHT = 0.25
INTEL_FILES_MAX = 4000


# ================================================================================= readers
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _at(value: Any) -> datetime | None:
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


# ================================================================================ the stages
def calls_by_model(now: datetime, window_days: float) -> dict[str, Any]:
    """Per (organ, model): parsed replies, empty replies, tokens, and the trailing empty streak."""
    rows = _jsonl(SPEND)
    if not rows and not SPEND.exists():
        return {"status": UNMEASURED, "source": str(SPEND.relative_to(REPO)),
                "why": "no spend ledger on this host"}
    cutoff = now - timedelta(days=window_days)
    agg: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        ts = _at(r.get("utc") or r.get("ts"))
        if ts is None:
            continue
        key = (str(r.get("organ") or r.get("seat") or "unknown"), str(r.get("model") or ""))
        a = agg.setdefault(key, {"ok": 0, "empty": 0, "tokens": 0, "streak": 0,
                                 "last_utc": "", "in_window": 0})
        empty = bool(r.get("empty_content"))
        a["streak"] = a["streak"] + 1 if empty else 0       # rows are append-ordered
        a["last_utc"] = ts.isoformat(timespec="seconds")
        if ts < cutoff:
            continue
        a["in_window"] += 1
        a["ok"] += 0 if empty else 1
        a["empty"] += 1 if empty else 0
        a["tokens"] += int(r.get("tokens") or 0)
    out = [{"organ": o, "model": m, "calls_parsed": a["in_window"], "ok": a["ok"],
            "empty": a["empty"], "tokens": a["tokens"], "empty_streak": a["streak"],
            "silent": a["streak"] >= SILENT_RUNS, "last_utc": a["last_utc"]}
           for (o, m), a in sorted(agg.items())]
    return {"status": "MEASURED", "source": str(SPEND.relative_to(REPO)),
            "note": "parsed replies only: a failed call writes no spend row (UNMEASURED stage)",
            "rows": out}


def panel_counters() -> dict[str, Any]:
    st = _read_json(PANEL)
    if not isinstance(st, dict):
        return {"status": UNMEASURED, "source": str(PANEL.relative_to(REPO))}
    calls = st.get("calls") or {}
    fails = st.get("failures") or {}
    models = sorted(set(calls) | set(fails))
    return {"status": "MEASURED", "source": str(PANEL.relative_to(REPO)), "scope": "lifetime",
            "rows": [{"model": m, "calls": int(calls.get(m) or 0),
                      "last_failure": fails.get(m)} for m in models]}


def lab_funnel() -> dict[str, Any]:
    doc = _read_json(LAB_ATTRIBUTION)
    if not isinstance(doc, dict):
        return {"status": UNMEASURED, "source": str(LAB_ATTRIBUTION.relative_to(REPO)),
                "why": "the third-brain lab's attribution feed is not on this host yet"}
    rows = []
    for model, r in sorted((doc.get("by_model") or {}).items()):
        if not isinstance(r, dict):
            continue
        calls = int(r.get("calls") or 0)
        compiled, judged, passed = (int(r.get(k) or 0) for k in ("compiled", "judged", "passed"))
        rows.append({"model": model, "calls": calls, "valid_json": int(r.get("valid_json") or 0),
                     "compiled": compiled, "judged": judged, "passed": passed,
                     "roi_per_call": round((compiled + PASS_WEIGHT * passed) / calls, 4)
                     if calls else None})
    return {"status": "MEASURED", "source": str(LAB_ATTRIBUTION.relative_to(REPO)),
            "rows": rows, "by_lab": doc.get("by_lab") or {}}


def proposals_by_model(now: datetime, window_days: float) -> dict[str, Any]:
    """Proposals that still carry the model that made them: seat queues and intelligence rows."""
    cutoff = (now - timedelta(days=window_days)).timestamp()
    counts: Counter[tuple[str, str]] = Counter()
    for q in sorted(SEAT_QUEUES.glob("*.json")) if SEAT_QUEUES.exists() else []:
        doc = _read_json(q)
        rows = doc if isinstance(doc, list) else (doc or {}).get("queue") or []
        for r in rows if isinstance(rows, list) else []:
            prov = r.get("provenance") if isinstance(r, dict) else None
            if isinstance(prov, dict) and prov.get("model"):
                counts[(f"seat:{q.stem}", str(prov["model"]))] += 1
    seen = 0
    for root in INTEL_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.json"):
            try:
                if p.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            seen += 1
            if seen > INTEL_FILES_MAX:
                break
            doc = _read_json(p)
            if isinstance(doc, dict):
                rows = doc.get("discoveries") or doc.get("rows") or []
            else:
                rows = doc if isinstance(doc, list) else []
            for r in rows if isinstance(rows, list) else []:
                if not isinstance(r, dict):
                    continue
                lin: dict[str, Any] = r["lineage"] if isinstance(r.get("lineage"), dict) else {}
                model = r.get("model") or lin.get("model")
                if model:
                    counts[(f"intel:{p.parent.name}", str(model))] += 1
    return {"status": "MEASURED",
            "note": "only rows that carry a model id; rows without one are attributed per seat "
                    "in generators[] and are UNMEASURED per model",
            "rows": [{"where": w, "model": m, "proposals": n}
                     for (w, m), n in sorted(counts.items())]}


def generators() -> dict[str, Any]:
    """Every producer PRODUCER_YIELD knows, joined to candidates, the registry funnel and certs."""
    py = _read_json(PRODUCER_YIELD)
    producers = (py or {}).get("producers") or [] if isinstance(py, dict) else []
    mc = _read_json(MINER_CANDIDATES)
    per_source = (mc or {}).get("per_source") or {} if isinstance(mc, dict) else {}
    cp = _read_json(CERT_PROVENANCE)
    certs = ((cp or {}).get("coverage") or {}).get("by_producer") or {} \
        if isinstance(cp, dict) else {}
    funnel: dict[str, dict[str, Any]] = {}
    try:
        with sqlite3.connect(f"file:{REGISTRY}?mode=ro", uri=True) as con:
            for row in con.execute("SELECT generator, generated, donated, judged, survivors, "
                                   "independent_survivors, compute_s, updated_at "
                                   "FROM generator_yield"):
                funnel[str(row[0])] = {"generated": row[1], "donated": row[2], "judged": row[3],
                                       "survivors": row[4], "independent_survivors": row[5],
                                       "compute_s": row[6], "updated_at": row[7]}
    except sqlite3.Error:
        funnel = {}
    rows = []
    names = {str(p.get("producer")) for p in producers if isinstance(p, dict)} | set(funnel)
    by_name = {str(p.get("producer")): p for p in producers if isinstance(p, dict)}
    for name in sorted(names):
        p = by_name.get(name, {})
        cand = per_source.get(name) or per_source.get(f"miner:{name}")
        rows.append({
            "generator": name,
            "verdict": p.get("verdict", UNMEASURED),
            "rows_in_window": p.get("rows_in_window"),
            "replacement": p.get("replacement"),
            "candidates": (cand.get("candidates") if isinstance(cand, dict) else cand),
            "funnel": funnel.get(name) or funnel.get(f"math:{name}"),
            "certs": certs.get(name) or certs.get(f"miner:{name}"),
        })
    math = {g: f for g, f in funnel.items() if g.startswith("math:")}
    return {"status": "MEASURED" if producers or funnel else UNMEASURED,
            "sources": {"producer_yield": (py or {}).get("generated_utc") if isinstance(py, dict)
                        else UNMEASURED,
                        "registry": "MEASURED" if funnel else UNMEASURED,
                        "certificate_provenance": (cp or {}).get("at") if isinstance(cp, dict)
                        else UNMEASURED},
            "math_traditions": math or UNMEASURED, "rows": rows}


def labs(now: datetime) -> dict[str, Any]:
    """The math, physics and world labs' own last pass: did it donate, and if not, why."""
    out: dict[str, Any] = {}
    for name, path in LAB_REPORTS.items():
        doc = _read_json(path)
        if not isinstance(doc, dict):
            out[name] = {"status": UNMEASURED, "source": str(path.relative_to(REPO))}
            continue
        at = _at(doc.get("at"))
        don: dict[str, Any] = doc["donation"] if isinstance(doc.get("donation"), dict) else {}
        age_h = round((now - at).total_seconds() / 3600, 2) if at else None
        out[name] = {"status": "MEASURED", "at": doc.get("at"), "age_h": age_h,
                     "dry_run": bool(doc.get("dry_run")),
                     "donated": int(don.get("donated") or doc.get("donated") or 0),
                     "donation_status": don.get("status", UNMEASURED),
                     "already_donated": don.get("already_donated_in_a_previous_pass"),
                     "refused_untradeable": don.get("refused_untradeable"),
                     "refused_wrong_lane": don.get("refused_wrong_lane"),
                     "refused_unstamped": don.get("refused_unstamped"),
                     "ledger": don.get("ledger"),
                     "by_tradition": don.get("by_tradition") or {}}
    return out


# ============================================================================ the red checks
def _replacement_target(text: Any) -> str:
    """The producer a free-text replacement names first (`"mathlab -- the ..."` -> mathlab)."""
    head = str(text or "").split("--", 1)[0].strip()
    return "" if not head or head.upper().startswith("NONE") else head.split()[0].strip(";,")


def violations(calls: dict[str, Any], gens: dict[str, Any],
               lab: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, r in (lab or {}).items():
        if r.get("status") != "MEASURED":
            continue
        if r["age_h"] is None or r["age_h"] > LAB_STALE_H:
            out.append({"check": "lab_clock_stale", "generator": name,
                        "why": f"{name}'s last report is {r['age_h']}h old (> {LAB_STALE_H}h)"})
        elif not r["dry_run"] and r["donated"] == 0:
            out.append({"check": "lab_gave_nothing", "generator": name,
                        "why": f"{name} ran {r['age_h']}h ago and donated 0: "
                               f"{r['donation_status']} (already donated "
                               f"{r['already_donated']}, untradeable "
                               f"{r['refused_untradeable']}, wrong lane "
                               f"{r['refused_wrong_lane']}, unstamped {r['refused_unstamped']})"})
    for r in calls.get("rows") or []:
        if r["silent"]:
            out.append({"check": "silent_success", "organ": r["organ"], "model": r["model"],
                        "why": f"last {r['empty_streak']} parsed replies were empty"})
    verdict = {g["generator"]: g["verdict"] for g in gens.get("rows") or []}
    for g in gens.get("rows") or []:
        if g["verdict"] != "DEAD":
            continue
        target = _replacement_target(g.get("replacement"))
        if target and verdict.get(target) == "DEAD":
            out.append({"check": "dead_replacement", "generator": g["generator"],
                        "replacement": target,
                        "why": f"{g['generator']} is DEAD and its declared replacement "
                               f"{target} is DEAD too"})
    return out


# ============================================================================== the budget
def priority(calls: dict[str, Any], lab: dict[str, Any]) -> dict[str, Any]:
    """model -> weight for the free panel. 1.0 is neutral; dead ids 0; silent ids SILENT_WEIGHT."""
    weights: dict[str, float] = {}
    why: dict[str, str] = {}
    for r in lab.get("rows") or []:
        if r["calls"] >= MIN_CALLS_FOR_WEIGHT and r["roi_per_call"] is not None:
            weights[r["model"]] = round(1.0 + 10.0 * float(r["roi_per_call"]), 4)
            why[r["model"]] = f"lab roi {r['roi_per_call']} over {r['calls']} calls"
    streaks: dict[str, int] = defaultdict(int)
    for r in calls.get("rows") or []:
        streaks[r["model"]] = max(streaks[r["model"]], r["empty_streak"])
    for model, streak in streaks.items():
        if streak >= SILENT_RUNS:
            weights[model] = SILENT_WEIGHT
            why[model] = f"{streak} empty replies in a row"
    try:
        from libs.ops import llm_seat
        dead_fn = getattr(llm_seat, "dead_models", None)
        dead = dead_fn("https://openrouter.ai/api/v1") if dead_fn else set()
    except Exception:
        dead = set()
    for model in dead:
        weights[model] = 0.0
        why[model] = "retired by the provider (llm_seat dead ledger)"
    return {"weights": dict(sorted(weights.items())), "why": why,
            "rule": "free_panel spreads calls by calls/weight; unlisted models weigh 1.0"}


# ==================================================================================== run
def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def run(*, window_days: float = WINDOW_DAYS, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    calls = calls_by_model(now, window_days)
    lab = lab_funnel()
    gens = generators()
    lab_runs = labs(now)
    for name, r in lab_runs.items():
        for tradition, n in (r.get("by_tradition") or {}).items():
            if isinstance(gens.get("math_traditions"), dict):
                gens["math_traditions"].setdefault(f"math:{tradition}", {})[
                    f"donated_last_pass_{name}"] = n
    bad = violations(calls, gens, lab_runs)
    prio = priority(calls, lab)
    return {"generated_utc": now.isoformat(timespec="seconds"), "window_days": window_days,
            "law": "every model and generator is measured to the certificate; silent success "
                   "and a dead replacement are RED; the budget follows conversion",
            "calls": calls, "panel": panel_counters(), "lab": lab,
            "proposals": proposals_by_model(now, window_days), "generators": gens,
            "labs": lab_runs,
            "priority": prio, "violations": bad, "red": bool(bad)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--window-days", type=float, default=WINDOW_DAYS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = run(window_days=args.window_days)
    _atomic(REPORT, doc)
    _atomic(PRIORITY, {"generated_utc": doc["generated_utc"], **doc["priority"]})
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"LLM_YIELD {'RED' if doc['red'] else 'ok'}: {len(doc['violations'])} violation(s); "
              f"calls {doc['calls']['status']}, lab {doc['lab']['status']}, "
              f"{len(doc['generators']['rows'])} generators")
    return 1 if doc["red"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
