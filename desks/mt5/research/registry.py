"""registry.py — permanent research knowledge ledger.

Every experiment ever run gets a permanent record: hypothesis, code_hash, data_hash,
parameters, instrument/TF/session/regime, side, costs, IS/OOS/WF/stress, gate outcomes,
PBO/DSR/placebo status, failure reason, live outcome (later). An LLM cannot rediscover
a failed strategy six months later — the registry is the memory.

Usage: python research/registry.py            (backfill all existing reports)
       python research/registry.py --hunt <file> <spec-json>  (append one record)
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
UNI = BASE / "data" / "universe"
LEDGER = REPORTS / "research_registry.jsonl"


def code_hash(path: Path) -> str:
    if not path.exists():
        return "?"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def data_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(UNI.glob("*_H1.parquet")):
        try:
            n = len(pd.read_parquet(p, columns=["close"]))
            h.update(f"{p.name}:{n}:".encode())
        except Exception:
            h.update(f"{p.name}:?".encode())
    return h.hexdigest()[:12]


def append(rec: dict) -> None:
    rec["ledger_at"] = datetime.now(timezone.utc).isoformat()
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def dedupe() -> int:
    if not LEDGER.exists():
        return 0
    seen: dict[str, int] = {}
    lines = LEDGER.read_text("utf-8").splitlines()
    out = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        key = (r.get("hunt_id"), r.get("code_hash"))
        if key in seen:
            seen[key] += 1
            continue
        seen[key] = 0
        out.append(ln)
    if len(out) != len(lines):
        LEDGER.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(lines) - len(out)


def backfill() -> None:
    hunts = {
        "hunt12": ("run_hunt12.py", "prior-NY mechanism state sweep: session-range breakout x day-state"),
        "hunt13": ("run_hunt13.py", "component decomposition of TREND_DAY state"),
        "hunt15": ("run_hunt15.py", "crisis/drawdown alpha miner (AUD family)"),
        "hunt16": ("run_hunt16.py", "Davidd corpus: 14 families x 2 sides x 4 windows x 2 states"),
        "hunt17": ("run_hunt17.py", "H4/D1 swing factory: 5 multi-TF families x LONG/SHORT x 2 params"),
        "hunt19": ("run_hunt19.py", "RFT corpus Tier S: Aroon+candle, retrack, RMI+inside, S/R reject, candle break, fail-seq"),
        "hunt20": ("run_hunt20.py", "SALEH corpus Tier S: squeeze, ema bank/runner, turtle, KAMA, alligator ablations, pairs RV"),
    }
    for hunt, (script, hyp) in hunts.items():
        fp = REPORTS / f"{hunt}.json"
        if not fp.exists():
            continue
        data = json.loads(fp.read_text("utf-8"))
        cells = data.get("all", [])
        sv = data.get("survivors", [])
        is_exp = float(pd.Series([c.get("exp", 0.0) for c in cells]).mean()) if cells else None
        is_t = float(pd.Series([c.get("t", 0.0) for c in cells]).mean()) if cells else None
        append({
            "hunt_id": hunt, "hypothesis": hyp,
            "code_hash": code_hash(BASE / "research" / script),
            "data_hash": data_hash(),
            "n_tests": len(cells), "n_survivors": len(sv),
            "is_mean_exp": round(is_exp, 4) if is_exp is not None and is_exp == is_exp else None,
            "is_mean_t": round(is_t, 4) if is_t is not None and is_t == is_t else None,
            "wf": "3-fold all>0 required" if cells else None,
            "stress": "2x costs exp>0 & t>1.5" if cells else None,
            "failure_reason": (f"{len(cells) - len(sv)} cells failed battery"
                               if not sv else None),
            "swept_at": data.get("swept_at"),
        })
    for extra, script, hyp in [
        ("DONE_placebo", "placebo_test.py", "bar-null placebo (4-bar blocks, 15 reps, 180 cells)"),
        ("DONE_regime_oos", "regime_discovery.py", "latent regime permission filter, OOS 30% fold validation"),
    ]:
        if (REPORTS / extra).exists():
            append({"hunt_id": extra.replace("DONE_", ""), "hypothesis": hyp,
                    "code_hash": code_hash(BASE / "research" / script),
                    "data_hash": data_hash(), "n_tests": None, "n_survivors": None,
                    "verdict": (json.loads((REPORTS / "latent_regimes.json").read_text("utf-8"))
                                .get("note") if extra == "DONE_regime_oos" else "CLEAN"),
                    "swept_at": (REPORTS / extra).read_text("utf-8")})


def append_hunt_record(hunt_id: str, spec: dict, report: dict) -> None:
    append({
        "hunt_id": hunt_id, "hypothesis": spec.get("hypothesis"),
        "geneology_id": spec.get("geneology_id"),
        "code_hash": code_hash(BASE / "research" / "run_hunt18.py"),
        "data_hash": data_hash(),
        "spec": spec,
        "n_tests": len(report.get("all", [])),
        "n_survivors": len(report.get("survivors", [])),
        "failure_reason": (f"{len(report.get('all', [])) - len(report.get('survivors', []))} "
                           f"cells failed battery" if not report.get("survivors") else None),
        "swept_at": report.get("swept_at"),
    })


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--hunt":
        spec = json.loads(sys.argv[3])
        report = json.loads((REPORTS / f"{sys.argv[2]}.json").read_text("utf-8"))
        append_hunt_record(sys.argv[2], spec, report)
        print("registry record appended", flush=True)
    else:
        backfill()
        print(f"backfill done, dupes removed: {dedupe()}",
              f"(ledger lines: {len(LEDGER.read_text('utf-8').splitlines()) if LEDGER.exists() else 0})",
              flush=True)