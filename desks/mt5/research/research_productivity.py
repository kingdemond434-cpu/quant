"""How fast the factory turns an idea into a verdict, and where it stalls.

Renaissance's stated investment was in making data immediately usable so an idea could be tested
quickly. The measurable form of that is latency and throughput at each stage of this desk's own
funnel, from the artifacts it already writes:

    intake         rows the miners produced                     data/intelligence/*/discoveries_*
    compiled       executable candidates the compiler admitted  data/hypotheses/miner_candidates
    deepened       tasks the deepening worker decided           data/hypotheses/deepening_worked
    judged         cells the gauntlet built and judged          reports/universal_gates_external
    certified      cells in the canon                           data/UNIVERSAL_SURVIVORS.canon
    forward        sleeves with a forward clock                 backups/moat/shadow_ledgers
    proposed       cells the proposers donated                  data/intelligence/{factor_residual,
                                                                plumbing,transition_alpha,...}
    recommended    recommendation ledger, open vs implemented   docs/research/recommendation_ledger

Per stage: count, count in the last 7 days, and where timestamps allow, the median age of items
that have NOT progressed -- which is the queue's latency, and the number that says which stage is
the bottleneck. A factory that certifies once a week from a thousand intake rows has a conversion
of 0.1%, and the stage where the other 999 stopped is the one to fix.
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
OUT = BASE / "reports" / "RESEARCH_PRODUCTIVITY.json"


def _mtime(p: Path) -> datetime:
    return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)


def _recent(paths: list[Path], days: int = 7) -> int:
    cut = datetime.now(tz=UTC) - timedelta(days=days)
    return sum(1 for p in paths if _mtime(p) >= cut)


def _rows(path: Path) -> list:
    try:
        d = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(d, list):
        return d
    for k in ("discoveries", "candidates", "verdicts", "tasks", "rows"):
        if isinstance(d.get(k), list):
            return d[k]
    return []


def stages() -> dict:
    intel = BASE / "data" / "intelligence"
    intake_files = [Path(p) for p in glob.glob(str(intel / "*" / "discoveries_*.json"))]
    intake_rows = sum(len(_rows(p)) for p in intake_files[-200:])
    proposers = {}
    for src in ("factor_residual", "plumbing", "transition_alpha", "weak_signal_ensemble"):
        fs = sorted(Path(p) for p in glob.glob(str(intel / src / "discoveries_*.json")))
        proposers[src] = {"files": len(fs), "rows_latest": len(_rows(fs[-1])) if fs else 0,
                          "last": (_mtime(fs[-1]).isoformat() if fs else None)}

    cand = _rows(BASE / "data" / "hypotheses" / "miner_candidates.json")
    deep_q = _rows(BASE / "data" / "hypotheses" / "miner_deepening_queue.json")
    worked = 0
    try:
        worked = sum(1 for ln in (BASE / "data" / "hypotheses" / "deepening_worked.jsonl")
                     .read_text("utf-8").splitlines() if ln.strip())
    except OSError:
        pass
    judged = _rows(BASE / "reports" / "universal_gates_external.json")
    try:
        canon = json.loads((BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json").read_text("utf-8"))
        certified = len(canon.get("survivors") or {})
        cert_dates = sorted(str(v.get("gated_at") or "")[:10]
                            for v in (canon.get("survivors") or {}).values()
                            if isinstance(v, dict) and v.get("gated_at"))
    except (OSError, ValueError):
        certified, cert_dates = 0, []
    ledgers = [Path(p) for p in glob.glob(str(ROOT / "backups" / "moat" / "shadow_ledgers"
                                             / "ledger_*.json"))]
    try:
        rec = json.loads((ROOT / "docs" / "research" / "recommendation_ledger.json")
                         .read_text("utf-8"))
        rec_rows = rec if isinstance(rec, list) else (rec.get("recommendations")
                                                       or rec.get("items") or [])
        rec_open = [r for r in rec_rows if isinstance(r, dict) and r.get("status") == "open"]
        ages = []
        for r in rec_open:
            try:
                ages.append((datetime.now(tz=UTC)
                             - datetime.fromisoformat(str(r["raised"]))).days)
            except (KeyError, ValueError, TypeError):
                pass
        rec_summary = {"total": len(rec_rows), "open": len(rec_open),
                       "open_median_age_days": (statistics.median(ages) if ages else None)}
    except (OSError, ValueError):
        rec_summary = {}

    return {
        "intake": {"files": len(intake_files), "files_7d": _recent(intake_files),
                   "rows_recent_files": intake_rows},
        "proposers": proposers,
        "compiled": {"candidates": len(cand)},
        "deepening": {"queued": len(deep_q), "decided_total": worked,
                      "backlog": max(0, len(deep_q) - worked)},
        "judged": {"cells": len(judged),
                   "unmeasured": sum(1 for v in judged if isinstance(v, dict) and v.get("unmeasured"))},
        "certified": {"cells": certified,
                      "last_certified": (cert_dates[-1] if cert_dates else None),
                      "certified_last_30d": sum(
                          1 for d in cert_dates
                          if d and d >= (datetime.now(tz=UTC) - timedelta(days=30)).strftime("%Y-%m-%d"))},
        "forward": {"sleeves_with_ledger": len(ledgers),
                    "ledgers_updated_7d": _recent(ledgers)},
        "recommendations": rec_summary,
    }


def run() -> dict:
    s = stages()
    conv = {}
    if s["intake"]["rows_recent_files"]:
        conv["intake_to_compiled"] = round(s["compiled"]["candidates"]
                                           / max(1, s["intake"]["rows_recent_files"]), 4)
    if s["judged"]["cells"]:
        conv["judged_to_certified"] = round(s["certified"]["cells"] / s["judged"]["cells"], 4)
    if s["certified"]["cells"]:
        conv["certified_to_forward"] = round(s["forward"]["sleeves_with_ledger"]
                                             / s["certified"]["cells"], 4)
    bottleneck = "deepening" if s["deepening"]["backlog"] > 100 else (
        "judged" if s["judged"]["cells"] and s["judged"]["unmeasured"] > 0.5 * s["judged"]["cells"]
        else "none obvious")
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "stages": s, "conversion": conv,
           "bottleneck": bottleneck}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    s = d["stages"]
    print(f"RESEARCH PRODUCTIVITY  bottleneck={d['bottleneck']}")
    print(f"  intake files={s['intake']['files']} (7d {s['intake']['files_7d']})  "
          f"compiled={s['compiled']['candidates']}  deepening backlog={s['deepening']['backlog']}")
    print(f"  judged={s['judged']['cells']} (unmeasured {s['judged']['unmeasured']})  "
          f"certified={s['certified']['cells']} (30d {s['certified']['certified_last_30d']})  "
          f"forward={s['forward']['sleeves_with_ledger']}")
    for k, v in s["proposers"].items():
        print(f"  proposer {k:22s} files={v['files']} latest_rows={v['rows_latest']}")
    print(f"  conversion: {d['conversion']}")
    print(f"  recommendations: {s['recommendations']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
