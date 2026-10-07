"""DID THE CRO's BREADTH STEPS ACTUALLY RUN? (breadth law, BREADTH-0162..0172)

The breadth-bottleneck CRO rule is ten steps (measure nominal vs effective certificates, name the
most saturated and the emptiest clusters, the compute spent in both, the leakage into saturated
ground, the redirect, distinct-cluster entry, evaluator admission, completed verdicts, and the
effective-breadth update after forward evidence) plus one law: a cycle is NOT successful merely
because more certificates were minted. `docs/cro/CRO_CYCLE.md` STEP 4D tells the lanes to do it.
Text is not evidence that it ran. This organ is.

For each step it reads TWO things and never infers either:

    the artifact   the report the step reads (CERTIFICATE_SATURATION, BREADTH_DEBT,
                   BREADTH_FEEDBACK, BREADTH_LADDER, JUDGE_COVERAGE, the verdict ledger,
                   EFFECTIVE_BREADTH); absent or older than ARTIFACT_MAX_AGE_H -> UNMEASURED
    the record     the newest `desks/mt5/data/cro_cycle_ledger.jsonl` row inside LEDGER_WINDOW_H
                   and the keys of its `breadth_law` block that the step must carry

and rules each step RAN (record carries the step's keys AND the artifact is fresh), MISSED (a
cycle row exists in the window without them) or UNMEASURED (no ledger, no row in the window, or
the artifact is absent / stale). UNMEASURED is never RAN and never zero (L1.28a).

THE SUCCESS LAW (0172). Across the last two `breadth_law` records: a cycle whose
n_certificates rose while n_effective_certificates did not is NOT_SUCCESS_NOMINAL_ONLY; one
where n_effective_certificates rose is SUCCESS_EFFECTIVE; fewer than two records is UNMEASURED.

Facts only: nothing here changes an order, a gate, a trial, capital, sizing or a promotion.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPORTS = DESK / "reports"
LEDGER = DESK / "data" / "cro_cycle_ledger.jsonl"
VERDICTS = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
OUT = REPORTS / "CRO_BREADTH_STEPS.json"
RAN, MISSED, UNMEASURED = "RAN", "MISSED", "UNMEASURED"
#: A cycle runs twice a day; a row older than this cannot speak for the current cycle.
LEDGER_WINDOW_H = 36.0
#: The step's artifact must be this fresh for the record to be about today's numbers.
ARTIFACT_MAX_AGE_H = 26.0
VERDICT_TAIL_BYTES = 4 * 1024 * 1024

#: (row, step, artifact, artifact keys that must be present, breadth_law keys the record carries)
STEPS: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("BREADTH-0162", "nominal_vs_effective", "CERTIFICATE_SATURATION.json",
     ("certificates",), ("n_certificates", "n_effective_certificates")),
    ("BREADTH-0163", "most_saturated", "CERTIFICATE_SATURATION.json",
     ("clusters",), ("n_saturated_clusters",)),
    ("BREADTH-0164", "emptiest_highest_value", "BREADTH_DEBT.json",
     ("empty_clusters",), ("top_debt",)),
    ("BREADTH-0165", "compute_in_both", "BREADTH_FEEDBACK.json",
     ("producers",), ("compute_saturated_vs_empty",)),
    ("BREADTH-0166", "leakage", "BREADTH_FEEDBACK.json",
     ("producers",), ("duplicate_survivor_share", "leaking_producers")),
    ("BREADTH-0167", "redirect", "BREADTH_LADDER.json",
     ("budget_split",), ("mode", "split")),
    ("BREADTH-0168", "distinct_cluster_entry", "BREADTH_FEEDBACK.json",
     ("producers",), ("new_structural_clusters",)),
    ("BREADTH-0169", "evaluator_admission", "JUDGE_COVERAGE.json",
     (), ("evaluator_admitted",)),
    ("BREADTH-0170", "completed_verdicts", "gate_verdict_ledger.jsonl",
     (), ("verdicts_completed",)),
    ("BREADTH-0171", "forward_breadth_update", "EFFECTIVE_BREADTH.json",
     ("effective",), ("n_effective_certificates", "forward_streams")),
)


def _parse(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def ledger_rows(path: Path | None = None) -> list[dict[str, Any]] | None:
    """Every parseable cycle row, oldest first; None when the ledger itself is absent."""
    p = path or LEDGER
    try:
        text = p.read_text("utf-8-sig")
    except OSError:
        return None
    rows: list[dict[str, Any]] = []
    for ln in text.splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def _breadth_law(row: Mapping[str, Any]) -> dict[str, Any]:
    bl = row.get("breadth_law")
    if isinstance(bl, str):
        try:
            bl = json.loads(bl)
        except ValueError:
            bl = None
    return dict(bl) if isinstance(bl, Mapping) else {}


def artifact_state(name: str, keys: tuple[str, ...], now: datetime,
                   reports: Path | None = None, verdicts: Path | None = None) -> dict[str, Any]:
    # the verdict ledger lives under data/hypotheses; every other artifact is a report
    p = (verdicts or VERDICTS) if name == VERDICTS.name else (reports or REPORTS) / name
    try:
        st = p.stat()
    except OSError:
        return {"artifact": name, "state": UNMEASURED, "why": "absent"}
    age_h = (now.timestamp() - st.st_mtime) / 3600.0
    out: dict[str, Any] = {"artifact": name, "age_h": round(age_h, 2)}
    if age_h > ARTIFACT_MAX_AGE_H:
        out.update(state=UNMEASURED, why=f"older than {ARTIFACT_MAX_AGE_H} h")
        return out
    if keys:
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            out.update(state=UNMEASURED, why="unreadable")
            return out
        missing = [k for k in keys if not isinstance(doc, Mapping) or doc.get(k) is None]
        if missing:
            out.update(state=UNMEASURED, why=f"keys absent: {missing}")
            return out
    out["state"] = "FRESH"
    return out


def success_law(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """BREADTH-0172 over the last two records that carry both counts."""
    recs = []
    for r in rows:
        bl = _breadth_law(r)
        try:
            n, k = float(bl["n_certificates"]), float(bl["n_effective_certificates"])
        except (KeyError, TypeError, ValueError):
            continue
        recs.append({"at": r.get("at"), "n": n, "k": k})
    if len(recs) < 2:
        return {"verdict": UNMEASURED, "why": f"{len(recs)} breadth_law record(s) with both counts"}
    a, b = recs[-2], recs[-1]
    if b["k"] > a["k"]:
        v = "SUCCESS_EFFECTIVE"
    elif b["n"] > a["n"]:
        v = "NOT_SUCCESS_NOMINAL_ONLY"
    else:
        v = "NO_BREADTH_GAIN"
    return {"verdict": v, "from": a, "to": b,
            "rule": "success is a rise in n_effective_certificates; more certificates alone is "
                    "NOT a successful cycle"}


def build(*, now: datetime | None = None, ledger: Path | None = None,
          reports: Path | None = None, verdicts: Path | None = None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    rows = ledger_rows(ledger)
    recent: dict[str, Any] | None = None
    why_none = ""
    if rows is None:
        why_none = "cro_cycle_ledger.jsonl absent on this host"
    else:
        dated = [(ts, r) for r in rows if (ts := _parse(r.get("at"))) is not None]
        inside = [(ts, r) for ts, r in dated
                  if (t - ts).total_seconds() / 3600.0 <= LEDGER_WINDOW_H]
        if inside:
            recent = max(inside, key=lambda x: x[0])[1]
        else:
            why_none = f"no cycle row in the last {LEDGER_WINDOW_H:.0f} h"
    bl = _breadth_law(recent) if recent else {}
    steps = []
    for row_id, step, art, akeys, lkeys in STEPS:
        a = artifact_state(art, akeys, t, reports, verdicts)
        rec: dict[str, Any] = {"row": row_id, "step": step, "artifact": a,
                               "record_keys": list(lkeys)}
        if recent is None:
            rec.update(state=UNMEASURED, why=why_none)
        elif a["state"] != "FRESH":
            rec.update(state=UNMEASURED, why=f"artifact {art}: {a.get('why')}")
        else:
            missing = [k for k in lkeys if bl.get(k) is None]
            if missing:
                rec.update(state=MISSED, why=f"cycle row {recent.get('at')} carries no "
                                             f"breadth_law {missing}")
            else:
                rec.update(state=RAN, cycle_at=recent.get("at"),
                           recorded={k: bl.get(k) for k in lkeys})
        steps.append(rec)
    counts = {s: sum(1 for r in steps if r["state"] == s) for s in (RAN, MISSED, UNMEASURED)}
    return {"status": UNMEASURED if recent is None else "MEASURED",
            "at": t.isoformat(timespec="seconds"),
            "cycle_row_at": recent.get("at") if recent else None,
            "cycle_lane": recent.get("lane") if recent else None,
            "why": why_none or None, "counts": counts, "steps": steps,
            "success_law": success_law(rows or []),
            "rule": (f"RAN = the newest cycle row within {LEDGER_WINDOW_H:.0f} h carries the "
                     f"step's breadth_law keys AND its artifact is under {ARTIFACT_MAX_AGE_H:.0f} "
                     "h old; MISSED = a row without them; UNMEASURED = no ledger / row / fresh "
                     "artifact. Never RAN by default.")}


def publish(doc: Mapping[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(p)
    return p
