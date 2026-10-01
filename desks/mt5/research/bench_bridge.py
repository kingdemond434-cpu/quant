#!/usr/bin/env python3
"""THE BRIDGE FROM RESEARCH BENCH TO CAPITAL, counted stage by stage and scored per candidate.

    python desks/mt5/research/bench_bridge.py [--out PATH]

WHAT IT REVERSE-ENGINEERS. Two practices the principal cited (2026-09-30). Scherman "backtested
thousands of models before putting hundreds of them to work", and the disclosed live example is
one pattern. The "Mini-Quant" one-person architecture runs gather -> generate -> backtest ->
STORE IN AN ALPHA POOL WITH A COMPOSITE SCORE -> execute, and the pool is the bridge. The shared
shape: a very large bench, a small deployed set, and an EXPLICIT scored door between them.

WHAT THE DESK HAS. Every piece of the door already exists and is automatic: the ten-gate
certificate (UNIVERSAL_SURVIVORS.json), forward enrolment of every certificate
(FORWARD_ENROLMENT.json), the promoter writing LIVE rows (data/sleeves.json), and the allocator's
marginal admission, which scores each candidate by dE[log W] against the book actually held
(pf_allocation.json `admission`). What did NOT exist is one place that counts the funnel end to
end and names, per candidate, where it stopped and what it would have added. Without that the
"small deployed set" is an accident of which stage is slow, not a decision.

THE SCORE IS dE[log W], NEVER A SHARPE RANK. The composite score of the Mini-Quant pool is
replaced by the only number this desk sizes by: the allocator's measured change in robust mean
log growth from adding the candidate to the held book at the same heat. Standalone Sharpe is
carried beside it so a reader sees where the two disagree.

IT CAPS NOTHING. The deployed count is whatever the survival-max solve funds. This report adds
no gate and no limit: its job is to make the missed growth visible -- a certified candidate with
positive dE[log W] that is not live is growth left on the bench, and it is listed first.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "desks" / "mt5"
OUT = BASE / "reports" / "BENCH_BRIDGE.json"
SOURCES = {
    "certified": BASE / "reports" / "UNIVERSAL_SURVIVORS.json",
    "forward": BASE / "reports" / "FORWARD_ENROLMENT.json",
    "live": BASE / "data" / "sleeves.json",
    "allocation": BASE / "reports" / "pf_allocation.json",
    "regime_contract": BASE / "reports" / "REGIME_ALLOCATION_CONTRACT.json",
}


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _read(p: Path) -> tuple[dict[str, Any] | None, str]:
    if not p.exists():
        return None, f"UNMEASURED: {_rel(p)} absent on this host"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"UNREADABLE: {type(exc).__name__}: {exc}"
    return (doc if isinstance(doc, dict) else {"rows": doc}), "MEASURED"


def _stage(n: int | None, status: str, **extra: Any) -> dict[str, Any]:
    return {"n": n, "status": status, **extra}


def build(sources: dict[str, Path] = SOURCES) -> dict[str, Any]:
    docs = {k: _read(p) for k, p in sources.items()}
    cert, cs = docs["certified"]
    fwd, fs = docs["forward"]
    live, ls = docs["live"]
    alloc, als = docs["allocation"]
    stages: dict[str, Any] = {}

    stages["certified_bench"] = _stage(
        int(cert.get("n") or len(cert.get("survivors") or {})) if cert else None, cs)
    stages["forward_enrolled"] = _stage(
        int(fwd["n_enrolled"]) if fwd and fwd.get("n_enrolled") is not None else None, fs,
        missing=(fwd or {}).get("n_missing"), overdue=(fwd or {}).get("n_overdue"))
    rows = (live or {}).get("sleeves") or []
    n_live = sum(1 for r in rows if isinstance(r, dict) and r.get("status") == "LIVE")
    n_standby = sum(1 for r in rows if isinstance(r, dict) and r.get("status") == "STANDBY")
    stages["live_rows"] = _stage(n_live if live else None, ls, standby=n_standby if live else None)

    book = {k: float(v) for k, v in ((alloc or {}).get("book") or {}).items()
            if isinstance(v, (int, float))}
    funded = {k: v for k, v in book.items() if v > 1e-6}
    stages["funded_by_allocator"] = _stage(len(funded) if alloc else None, als,
                                           total_heat=round(sum(funded.values()), 6)
                                           if alloc else None)
    adm = (alloc or {}).get("admission") or {}
    cands = adm.get("candidates") or {}
    live_names = {str(r.get("name")) for r in rows if isinstance(r, dict)
                  and r.get("status") == "LIVE"}

    scored = []
    for name, row in cands.items():
        if not isinstance(row, dict):
            continue
        d = row.get("delta_elogw_per_day")
        scored.append({"candidate": name, "delta_elogw_per_day": d,
                       "delta_elogw_per_year": row.get("delta_elogw_per_year"),
                       "sharpe_standalone_annual": row.get("sharpe_standalone_annual"),
                       "corr_to_book": row.get("corr_to_book"),
                       "admitted": name in (adm.get("admitted") or []),
                       "funded": name in funded, "live_row": name in live_names})
    scored.sort(key=lambda r: -(r["delta_elogw_per_day"]
                                if isinstance(r["delta_elogw_per_day"], (int, float)) else -1e9))
    missed = [r for r in scored if isinstance(r["delta_elogw_per_day"], (int, float))
              and r["delta_elogw_per_day"] > 0 and not r["funded"]]
    dead_weight = sorted(n for n in live_names if n not in funded and funded)

    funnel = [stages[k]["n"] for k in ("certified_bench", "forward_enrolled", "live_rows",
                                       "funded_by_allocator")]
    conv = {}
    labels = ("bench_to_forward", "forward_to_live", "live_to_funded")
    for i, lab in enumerate(labels):
        a, b = funnel[i], funnel[i + 1]
        conv[lab] = round(b / a, 4) if isinstance(a, int) and a > 0 and isinstance(b, int) else None

    a, b = funnel[0], funnel[2]
    conv["bench_to_live"] = round(b / a, 4) if isinstance(a, int) and a > 0 and isinstance(b, int) else None
    rc, rcs = docs["regime_contract"]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "stages": stages, "conversion": conv,
        "missed_growth": missed[:25],
        "missed_growth_per_year": round(sum(float(r["delta_elogw_per_year"] or 0.0)
                                            for r in missed), 6) if missed else 0.0,
        "live_but_unfunded": dead_weight,
        "scored_candidates": scored[:100], "n_scored": len(scored),
        "regime_contract": {"status": rcs, "verdict": (rc or {}).get("verdict")},
        "rule": ("score = the allocator's dE[log W] of adding the candidate to the held book at "
                 "the same heat; missed growth = positive score and unfunded. Caps nothing: the "
                 "deployed count is what the survival-max solve funds."),
        "sources": {k: _rel(p) for k, p in sources.items()},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(json.dumps({"stages": {k: v["n"] for k, v in doc["stages"].items()},
                      "conversion": doc["conversion"],
                      "missed_growth": len(doc["missed_growth"])}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
