#!/usr/bin/env python3
"""THE EVIDENCE EACH ARCH-30 PASS QUESTION NEEDS, MEASURED BEFORE THE PASS ASKS IT.

    python scripts/check_pass_question_evidence.py [--root <repo>] [--out <json>]
        [--now <iso>] [--since <iso>] [--max-age-h 26]

Clock: hourly leg `pass_question_evidence` (desks/mt5/research/hourly_cycle.py). Artifact:
desks/mt5/reports/PASS_QUESTION_EVIDENCE.json. Read by the CRO pass at STEP 4B before it
answers Q1-Q7 (docs/cro/CRO_CYCLE.md, PASS QUESTIONS).

WHY (ARCH-30, principal 2026-10-06). Every pass must answer seven questions with box evidence,
and `scripts/check_cro_duties.py --review` rewrites an answer MISSED when its citation does not
resolve. That enforcement is live; what was missing is the evidence. No organ said which
artifacts answer which question, whether they were fresh, or which parts of a question NOTHING
on the desk measures -- so a pass could only cite what it happened to find, and a question with
no measuring organ read MISSED every pass with no owner told why.

WHAT IT WRITES, per question:
  * `sub_measures`: each named part of the question, the artifact and key that measure it, and
    FRESH / STALE / ABSENT / UNSTAMPED / KEY_ABSENT -- or NO_ORGAN, with the owner the gap is
    routed to, when nothing on the desk measures that part;
  * `citations`: `<path>@<stamp>` strings in exactly the form `check_cro_duties.citation_resolves`
    accepts, built from each FRESH artifact's own stamp, so the pass can paste them;
  * `status`: MEASURED (every part fresh), PARTIAL, or UNMEASURED (nothing fresh). An absent
    input is UNMEASURED, never a clean pass (L1.28a), and a NO_ORGAN part keeps a question
    PARTIAL at best.

Q2 IS COMPUTED HERE, NOT ONLY LOCATED. "Which producers added distinct validated information"
is answered per producer from the certificates gated since `--since` (default one pass window):
each survivor's family is classified into its declared payer cluster
(`libs/research/alpha_clusters.classify_family`) and credited with the marginal effective
breadth it buys the book (`libs/research/breadth_credit.marginal_k_eff`: the cross-cluster rho
for a new cluster, the book's own implied rho for an occupied one). Cell and candidate counts do
not count, a producer with zero gain is named, and an UNCLASSIFIED survivor is counted apart,
never credited.

Report only. It reads, it never sizes, vetoes or throttles anything. Exits 0 when every question
is MEASURED or PARTIAL with no NO_ORGAN part, and 2 (a declared verdict exit for this leg) when
any question is UNMEASURED or any part has no organ: the RED names who must build it.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import check_cro_duties as duties  # noqa: E402

from libs.ops.win_write import write_text_resilient  # noqa: E402
from libs.research.alpha_clusters import UNCLASSIFIED, classify_family  # noqa: E402
from libs.research.breadth_credit import MEASURED, book_state, marginal_k_eff  # noqa: E402

OUT = ROOT / "desks" / "mt5" / "reports" / "PASS_QUESTION_EVIDENCE.json"
MAX_AGE_H = 26.0
EXIT_RED = 2
FUTURE_SLACK = timedelta(minutes=10)

GROWTH_ALLOCATOR = "desktop 'Growth allocator overhaul' session (money path)"
DESK_HEALTH = "Desk health thread"

#: Q -> (question, sub-measures). A sub-measure is (name, artifact, key) where `key` is looked
#: up anywhere in the artifact (`check_cro_duties.find_key`), or (name, None, owner) for a part
#: of the question no organ on the desk measures yet: NO_ORGAN, routed to `owner`.
QUESTIONS: dict[str, tuple[str, list[tuple[str, str | None, str]]]] = {
    "Q1": ("What is the best work waiting?", [
        ("rails_costing_growth", "reports/MISSED_GROWTH.json", "costs_growth"),
        ("work_not_tested", "reports/opportunity_cost.json", "not_tested"),
        ("research_value_by_source", "reports/RESEARCH_ROI.json", "roi"),
    ]),
    "Q2": ("Which producers added distinct validated information?", [
        ("certificates", "reports/UNIVERSAL_SURVIVORS.json", "survivors"),
        ("book_breadth", "reports/EFFECTIVE_BREADTH.json", "effective"),
        ("producer_roster", "reports/PRODUCER_YIELD.json", "producers"),
    ]),
    "Q3": ("What opportunities were missed?", [
        ("missed_growth_rails", "reports/MISSED_GROWTH.json", "rails"),
        ("missed_trades", "reports/MISSED_TRADES.json", "episodes"),
        ("refusals", "reports/WHY_NOT.json", "at"),
    ]),
    "Q4": ("Did the allocator beat its baselines?", [
        ("baseline_contest", "reports/ALLOCATOR_PROOF.json", "scores"),
        ("best_single_sleeve_baseline", None, GROWTH_ALLOCATOR),
        ("executable_book_after_lots_and_costs", None, GROWTH_ALLOCATOR),
    ]),
    "Q5": ("What did stale information, costs or defects cost?", [
        ("cost_vs_model", "reports/COST_TRUTH.json", "total_overcharge"),
        ("stale_desk_inputs", "reports/DESK_STALE.json", "verdict"),
        ("stale_swap_costs", "reports/BROKER_SWAPS_FRESHNESS.json", "at"),
        ("fail_closed_rail_costs", "reports/MISSED_GROWTH.json", "rails"),
        ("defect_loss_in_elog", None, DESK_HEALTH),
    ]),
    "Q6": ("Which components can be removed?", [
        ("dead_architecture", "reports/dead_architecture.json", "organs"),
        ("silent_organs", "reports/SILENT_ORGANS.json", "at"),
    ]),
    "Q7": ("What is the most valuable new capability?", [
        ("unseen_frontier", "reports/UNSEEN_FRONTIER.json", "at"),
        ("limitations_and_next_experiment", "reports/META_RND.json", "at"),
        ("research_value_by_source", "reports/RESEARCH_ROI.json", "roi"),
    ]),
}


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _summary(v: Any) -> Any:
    """A short reading of a counter: its length for a container, else the scalar itself."""
    if isinstance(v, Mapping):
        return {"n": len(v)}
    if isinstance(v, list):
        return {"n": len(v)}
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v if not isinstance(v, str) else v[:200]
    return str(v)[:200]


def read_artifact(rel: str, root: Path, now: datetime, max_age_h: float) -> dict[str, Any]:
    """{path, state, stamp, stamp_source, age_h, doc} -- state FRESH/STALE/ABSENT/UNSTAMPED."""
    path = duties.resolve(rel, root)
    shown = path.relative_to(root).as_posix() if path.is_relative_to(root) else rel
    out: dict[str, Any] = {"path": shown, "doc": None, "stamp": None, "stamp_source": None,
                           "age_h": None}
    if not path.is_file():
        return {**out, "state": "ABSENT"}
    doc, err = duties._load(path)
    if err:
        return {**out, "state": "ABSENT", "why": err}
    ts, src = duties._stamp(doc, path, root)
    out.update(doc=doc, stamp_source=src)
    if ts is None:
        return {**out, "state": "UNSTAMPED"}
    out.update(stamp=_iso(ts), age_h=round((now - ts) / timedelta(hours=1), 2))
    if ts > now + FUTURE_SLACK:
        return {**out, "state": "STALE", "why": "stamped in the future"}
    return {**out, "state": "FRESH" if out["age_h"] <= max_age_h else "STALE"}


def _spec(row: Mapping[str, Any]) -> Mapping[str, Any]:
    spec = row.get("shadow_spec")
    return spec if isinstance(spec, Mapping) else {}


def producer_of(row: Mapping[str, Any]) -> str:
    """Which producer made a certificate: its declared provenance, else the hunt that judged it."""
    spec = _spec(row)
    for src in (row, spec):
        for k in ("producer", "source", "seat"):
            v = src.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    hunt = row.get("hunt") or spec.get("hunt")
    return f"hunt:{hunt}" if hunt else "UNATTRIBUTED"


def producer_gain(survivors: Any, breadth: Any, roster: Any, since: datetime,
                  now: datetime) -> dict[str, Any]:
    """Q2: per producer, the k_eff and independent-cluster gain of what it validated since
    `since`. Survivors are credited in the order they were gated, each against the book as the
    previous ones left it, so two producers landing the same new cluster are not both paid."""
    state = book_state(breadth if isinstance(breadth, Mapping) else {})
    if state.get("status") != MEASURED:
        return {"status": "UNMEASURED", "why": state.get("why", "no breadth reading")}
    rows = (list(survivors.values()) if isinstance(survivors, Mapping)
            else survivors if isinstance(survivors, list) else None)
    if rows is None:
        return {"status": "UNMEASURED", "why": "the certificate registry has no survivor list"}
    fresh: list[tuple[datetime, Mapping[str, Any]]] = []
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        t = duties._parse_ts(r.get("gated_at"))
        if t is not None and since <= t <= now + FUTURE_SLACK:
            fresh.append((t, r))
    fresh.sort(key=lambda x: x[0])
    n, k = state["n_nominal"], state["k_eff"]
    occupied = set(state["occupied"])
    clusters_before = len(occupied)
    per: dict[str, dict[str, Any]] = {}
    for _, r in fresh:
        spec = _spec(r)
        family = str(spec.get("family") or r.get("family") or "")
        who = producer_of(r)
        p = per.setdefault(who, {"producer": who, "validated": 0, "delta_k_eff": 0.0,
                                 "new_clusters": [], "unclassified": 0})
        p["validated"] += 1
        cluster = classify_family(family) if family else UNCLASSIFIED
        if cluster == UNCLASSIFIED:
            p["unclassified"] += 1           # a payer the desk cannot name is never credited
            continue
        new = cluster not in occupied
        rho = state["rho_cross"] if new else state["rho_book"]
        try:
            dk = marginal_k_eff(n, k, rho)
        except ValueError:
            continue
        n, k = n + 1.0, k + dk
        p["delta_k_eff"] += dk
        if new:
            occupied.add(cluster)
            p["new_clusters"].append(cluster)
    for p in per.values():
        p["delta_k_eff"] = round(p["delta_k_eff"], 6)
    ranked = sorted(per.values(), key=lambda p: -p["delta_k_eff"])
    zero = sorted(p["producer"] for p in ranked if p["delta_k_eff"] <= 0 and not p["new_clusters"])
    # A producer on the roster that validated nothing this window gained nothing: named.
    names: set[str] = set()
    for item in roster if isinstance(roster, list) else []:
        if isinstance(item, Mapping) and isinstance(item.get("producer"), str):
            names.add(item["producer"])
    silent = sorted(names - set(per))
    if not all(math.isfinite(v) for v in (n, k)):
        return {"status": "UNMEASURED", "why": "the breadth arithmetic did not stay finite"}
    return {"status": "MEASURED", "since": _iso(since), "certificates_in_window": len(fresh),
            "k_eff_before": round(state["k_eff"], 6), "k_eff_after": round(k, 6),
            "clusters_before": clusters_before, "clusters_after": len(occupied),
            "producers": ranked, "zero_gain_producers": zero,
            "roster_producers_with_no_certificate": len(silent),
            "roster_producers_with_no_certificate_sample": silent[:50],
            "rule": ("gain = sum of marginal k_eff over the producer's certificates gated in the "
                     "window, in gating order; rho = cross-cluster for a new payer cluster, the "
                     "book's implied rho for an occupied one; UNCLASSIFIED is never credited; a "
                     "certificate with no declared producer is attributed to its hunt")}


def allocator_vs_baselines(proof: Any) -> dict[str, Any]:
    """Q4, as far as the contest measures it: the dynamic book's robust score against every
    contested baseline, and which baselines beat it (each a finding for the allocator session)."""
    scores = proof.get("scores") if isinstance(proof, Mapping) else None
    if not isinstance(scores, Mapping) or not isinstance(scores.get("dynamic"), Mapping):
        return {"status": "UNMEASURED", "why": "the proof carries no dynamic score"}

    def _s(v: Any) -> float | None:
        x = v.get("robust_score") if isinstance(v, Mapping) else None
        return float(x) if isinstance(x, (int, float)) and math.isfinite(float(x)) else None

    dyn = _s(scores["dynamic"])
    if dyn is None:
        return {"status": "UNMEASURED", "why": "the dynamic score is not a finite number"}
    rivals = {str(k): _s(v) for k, v in scores.items() if k != "dynamic"}
    beat_by = sorted(k for k, v in rivals.items() if v is not None and v > dyn)
    return {"status": "MEASURED", "dynamic_robust_score": dyn,
            "baselines": dict(sorted(rivals.items())),
            "baselines_beating_dynamic": beat_by, "passed": proof.get("passed"),
            "basis": ("sampled worlds at equal total heat (libs/portfolio/allocator_proof); "
                      "NOT the executable book after lot rounding and costs, and no "
                      "best-single-sleeve rival is contested -- both are NO_ORGAN below"),
            "route": GROWTH_ALLOCATOR if beat_by else None}


def measure(root: Path = ROOT, now: datetime | None = None, since: datetime | None = None,
            max_age_h: float = MAX_AGE_H) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    since = since or now - timedelta(hours=max_age_h)
    cache: dict[str, dict[str, Any]] = {}
    questions: dict[str, Any] = {}
    no_organ: list[dict[str, str]] = []
    for q, (text, subs) in QUESTIONS.items():
        rows: list[dict[str, Any]] = []
        cites: list[str] = []
        for name, rel, key in subs:
            if rel is None:
                rows.append({"name": name, "state": "NO_ORGAN", "owner": key,
                             "why": "no organ on the desk measures this part of the question"})
                no_organ.append({"question": q, "part": name, "owner": key})
                continue
            art = cache.get(rel) or read_artifact(rel, root, now, max_age_h)
            cache[rel] = art
            row = {"name": name, "artifact": art["path"], "key": key, "state": art["state"],
                   "stamp": art["stamp"], "age_h": art["age_h"]}
            if art["state"] == "FRESH":
                found, val = duties.find_key(art["doc"], key)
                if found:
                    row["reading"] = _summary(val)
                    cite = f"{art['path']}@{art['stamp']}"
                    if cite not in cites:
                        cites.append(cite)
                else:
                    row["state"] = "KEY_ABSENT"
            rows.append(row)
        measured = [r for r in rows if r["state"] == "FRESH"]
        organ = [r for r in rows if r["state"] != "NO_ORGAN"]
        status = ("UNMEASURED" if not measured
                  else "MEASURED" if len(measured) == len(rows) else "PARTIAL")
        entry: dict[str, Any] = {"question": text, "status": status, "citations": cites,
                                 "sub_measures": rows,
                                 "fresh": len(measured), "measurable": len(organ),
                                 "parts": len(rows)}
        questions[q] = entry

    q2 = questions["Q2"]
    arts = {r["name"]: r for r in q2["sub_measures"]}
    if arts["certificates"]["state"] == "FRESH" and arts["book_breadth"]["state"] == "FRESH":
        roster = cache["reports/PRODUCER_YIELD.json"]
        q2["producer_gain"] = producer_gain(
            (cache["reports/UNIVERSAL_SURVIVORS.json"]["doc"] or {}).get("survivors"),
            cache["reports/EFFECTIVE_BREADTH.json"]["doc"],
            (roster["doc"] or {}).get("producers") if roster["state"] == "FRESH" else None,
            since, now)
    else:
        q2["producer_gain"] = {"status": "UNMEASURED",
                               "why": "certificates or book breadth not fresh on this host"}
    if q2["producer_gain"].get("status") != "MEASURED" and q2["status"] == "MEASURED":
        q2["status"] = "PARTIAL"

    q4 = questions["Q4"]
    proof = cache["reports/ALLOCATOR_PROOF.json"]
    q4["contest"] = (allocator_vs_baselines(proof["doc"]) if proof["state"] == "FRESH"
                     else {"status": "UNMEASURED", "why": f"ALLOCATOR_PROOF {proof['state']}"})

    unmeasured = sorted(q for q, v in questions.items() if v["status"] == "UNMEASURED")
    red = bool(unmeasured or no_organ)
    return {"at": _iso(now), "since": _iso(since), "max_age_h": max_age_h,
            "status": "RED" if red else "GREEN",
            "questions": questions, "unmeasured_questions": unmeasured,
            "no_organ": no_organ,
            "why": (f"{len(unmeasured)} question(s) with no fresh evidence, "
                    f"{len(no_organ)} part(s) no organ measures"),
            "rule": ("cite `citations` verbatim in TIER1_BREADTH_REVIEW.json pass_questions; a "
                     "question here UNMEASURED cannot be ANSWERED this pass (L1.28a), and a "
                     "NO_ORGAN part is routed to its owner, never answered from prose"),
            "source": "scripts/check_pass_question_evidence.py"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--now", help="ISO timestamp to measure against (tests); default now, UTC")
    ap.add_argument("--since", help="window start for Q2; default now - max-age-h")
    ap.add_argument("--max-age-h", type=float, default=MAX_AGE_H)
    a = ap.parse_args(argv)
    now = duties._parse_ts(a.now) if a.now else datetime.now(UTC)
    since = duties._parse_ts(a.since) if a.since else None
    if now is None:
        ap.error("--now is not an ISO timestamp")
    root = a.root.resolve()
    doc = measure(root, now, since, a.max_age_h)
    out = a.out or (root / OUT.relative_to(ROOT))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_text_resilient(out, json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({"status": doc["status"], "unmeasured": doc["unmeasured_questions"],
                      "no_organ": len(doc["no_organ"]),
                      "by_q": {q: v["status"] for q, v in doc["questions"].items()}}))
    return 0 if doc["status"] == "GREEN" else EXIT_RED


if __name__ == "__main__":
    sys.exit(main())
