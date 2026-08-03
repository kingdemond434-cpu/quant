#!/usr/bin/env python3
"""DATA DECAY MONITOR -- triage #97, the last unblocked BUILD item.

WHY IT COULD NOT BE BUILT BEFORE, AND WHY THAT STOPPED BEING TRUE. Its blocker read "needs
dataset-usefulness history; nothing to trend yet". Two producers now write that history:
`data/canary_history.jsonl` records per-source reachability every run, and
`data/acquisition_history.jsonl` records per-candidate usefulness scores. Between them the desk can
trend both halves of decay -- a source going dark, and a source going useless while still
answering -- which are different failures with opposite remedies and are never summed here.

WHAT IT REFUSES TO DO. It will not call a source decayed because nobody measured it lately. The
three states that all look like "low recent reading" are separated explicitly: NEVER-WORKED (an
acquisition failure, not a decline), UNDERPOWERED (the sample cannot tell), and DECAYING. The
desk's own recurring defect is the detector that reads "not measured" as "measured and fine"; the
inverse error, killing a live source on a thin sample, is equally available here and equally
refused.

Read-only over data/. Writes one artifact. No network, no keys, no order paths.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.decay import classify_decay  # noqa: E402

CANARY = ROOT / "data/canary_history.jsonl"
ACQUIRE = ROOT / "data/acquisition_history.jsonl"
REPORT = ROOT / "data/data_decay.json"

#: Verdicts that mean "act". Everything else is reported and acted on by nobody, on purpose.
ACTIONABLE = ("DECAYING", "DEAD")


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue                      # a corrupt line is skipped, never guessed at
    return out


def _ts(row: dict) -> float | None:
    raw = row.get("ts")
    if isinstance(raw, int | float):
        return float(raw)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw).timestamp()
        except ValueError:
            return None
    return None


def availability_points() -> dict[str, list[tuple[float, float]]]:
    """source -> [(ts, 1.0 reachable / 0.0 not)] from the canary history.

    The canary labels each probe with a human name; that label is the source identity, because the
    C1/C2 keys are positional and shift the moment a probe is added or removed. Keying on position
    would silently splice two different sources' histories into one trend.
    """
    pts: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in _rows(CANARY):
        ts = _ts(row)
        if ts is None:
            continue
        for key, res in (row.get("results") or {}).items():
            if not isinstance(res, dict):
                continue
            name = str(res.get("label") or key)
            bad = str(res.get("verdict", "")).upper() in {"UNREACHABLE", "ERROR", "FAILED"}
            pts[name].append((ts, 0.0 if bad else 1.0))
    return dict(pts)


def usefulness_points() -> dict[str, list[tuple[float, float]]]:
    """source -> [(ts, score)] from the acquisition history's per-run top candidates."""
    pts: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in _rows(ACQUIRE):
        ts = _ts(row)
        if ts is None:
            continue
        for cand in row.get("top") or []:
            if not isinstance(cand, dict):
                continue
            name = str(cand.get("source") or cand.get("name") or "")
            score = cand.get("score")
            if name and isinstance(score, int | float):
                pts[name].append((ts, float(score)))
    return dict(pts)


def main() -> int:
    avail, useful = availability_points(), usefulness_points()
    results = [classify_decay(s, p, kind="availability").__dict__ for s, p in sorted(avail.items())]
    results += [classify_decay(s, p, kind="usefulness").__dict__ for s, p in sorted(useful.items())]

    tally: dict[str, int] = {}
    for r in results:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    act = [r for r in results if r["verdict"] in ACTIONABLE]

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "inputs": {"canary": _rel(CANARY), "canary_rows": len(_rows(CANARY)),
                   "acquisition": _rel(ACQUIRE), "acquisition_rows": len(_rows(ACQUIRE))},
        "sources": len(results), "tally": tally,
        "actionable": [{"source": r["source"], "kind": r["kind"], "verdict": r["verdict"],
                        "why": r["why"]} for r in act],
        "results": results,
        "note": ("AVAILABILITY and USEFULNESS are reported separately and never summed: a source "
                 "going dark needs a new endpoint, a source going useless needs retiring, and an "
                 "average of the two recommends neither. NEVER-WORKED is not decay -- nothing "
                 "declined -- and UNDERPOWERED is not health: readings are collapsed to one per "
                 "hour, so a burst of identical rows buys one observation, which is what it is "
                 "worth."),
        "authority": "NONE. Reports decay; retires nothing and acquires nothing.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    print(f"data-decay: {len(results)} source-metric(s) "
          f"from {out['inputs']['canary_rows']} canary + "
          f"{out['inputs']['acquisition_rows']} acquisition row(s)")
    for v, c in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {v:<14} {c}")
    for r in act[:10]:
        print(f"  ACT {r['kind'][:4]} {r['source'][:44]:<44} {r['verdict']}")
    if not results:
        print("  no history yet -- canary/acquisition producers write it; data/ is gitignored, so "
              "an empty read is expected in a fresh checkout and REAL on the VPS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
