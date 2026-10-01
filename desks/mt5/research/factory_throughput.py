"""THE FACTORY THROUGHPUT BENCHMARK -- expression_factory against EasyQuant's published loop.

EasyQuant's LLM factor loop reports 8 candidates per 15 minutes WITH auto-backtest and
walk-forward, i.e. 32 per hour. The desk's comparable stage is the factory's TIER 1: every cell
that reaches it is backtested on the symbol's own bars with the direction chosen on the first 60%
of trades and every number reported on the last 40% (an out-of-sample walk-forward split), plus a
null factory. This organ publishes, every hour, from the factory's OWN last report and campaign
journal -- never from a constant:

  candidates per hour     generated (tier 0), backtested out of sample (tier 1), queued to the
                          one judge -- per wall-hour of factory compute and per clock hour (the
                          factory runs once an hour, so a pass's count IS its hourly yield)
  stage profile           the factory's `stage_seconds` (evaluate, cheap layer, tier 1, tier 2,
                          parent selection), and which stage is the largest share
  pipeline latency        from `data/expression_factory/campaign.jsonl`: first transition ->
                          QUEUED -> TESTING -> verdict (FORWARD | FAILED), p50 / p90 in hours,
                          plus the count and age of queued cells with no verdict yet (censored:
                          they are reported, never dropped from the median silently)
  the bottleneck          the stage with the largest share of the whole idea-to-verdict path

UNMEASURED IS NEVER ZERO: an absent report, a report with no `stage_seconds` (written before the
profile landed), or an empty journal each read UNMEASURED with the reason.

    python desks/mt5/research/factory_throughput.py --once
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
FACTORY_REPORT = DESK / "reports" / "EXPRESSION_FACTORY.json"
JOURNAL = DESK / "data" / "expression_factory" / "campaign.jsonl"
OUT = DESK / "reports" / "FACTORY_THROUGHPUT.json"
UNMEASURED = "UNMEASURED"
#: EasyQuant's published rate: 8 candidates per 15 minutes, each auto-backtested and
#: walk-forward validated.
EASYQUANT_PER_HOUR = 8 * 4
JOURNAL_TAIL_BYTES = 64 * 1024 * 1024


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _ts(s: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def journal(path: Path = JOURNAL) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > JOURNAL_TAIL_BYTES:
                fh.seek(size - JOURNAL_TAIL_BYTES)
                fh.readline()
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        pass
    return out


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    k = min(len(xs) - 1, max(0, round(q * (len(xs) - 1))))
    return round(xs[k], 3)


def latency(rows: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Per campaign key: first seen, QUEUED, TESTING and verdict times -> hours between them."""
    if not rows:
        return {"status": UNMEASURED, "why": f"{JOURNAL.name} absent or empty on this host"}
    first: dict[str, datetime] = {}
    queued: dict[str, datetime] = {}
    verdict: dict[str, tuple[datetime, str]] = {}
    for r in rows:
        k, at = str(r.get("key") or ""), _ts(r.get("at"))
        if not k or at is None:
            continue
        first.setdefault(k, at)
        to = str(r.get("to") or "")
        if to == "QUEUED":
            queued.setdefault(k, at)
        elif to in ("FORWARD", "FAILED") and k in queued:
            verdict.setdefault(k, (at, to))
    q_to_v = [(verdict[k][0] - queued[k]).total_seconds() / 3600 for k in verdict]
    f_to_q = [(queued[k] - first[k]).total_seconds() / 3600 for k in queued]
    f_to_v = [(verdict[k][0] - first[k]).total_seconds() / 3600 for k in verdict]
    waiting = [(now - queued[k]).total_seconds() / 3600 for k in queued if k not in verdict]
    return {"status": "MEASURED", "keys": len(first), "queued": len(queued),
            "judged": len(verdict), "forward": sum(1 for v in verdict.values()
                                                   if v[1] == "FORWARD"),
            "first_to_queued_h": {"p50": _pct(f_to_q, 0.5), "p90": _pct(f_to_q, 0.9)},
            "queued_to_verdict_h": {"p50": _pct(q_to_v, 0.5), "p90": _pct(q_to_v, 0.9)},
            "idea_to_verdict_h": {"p50": _pct(f_to_v, 0.5), "p90": _pct(f_to_v, 0.9)},
            "awaiting_verdict": {"n": len(waiting), "age_p50_h": _pct(waiting, 0.5),
                                 "age_max_h": round(max(waiting), 2) if waiting else None},
            "censoring": ("cells queued with no verdict yet are counted in awaiting_verdict and "
                          "NOT in the verdict percentiles, which therefore understate the path")}


def build(now: datetime | None = None, *, report: Any = None,
          rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rep = report if report is not None else _read(FACTORY_REPORT)
    lat = latency(rows if rows is not None else journal(), now)
    doc: dict[str, Any] = {"generated_utc": now.isoformat(), "writer":
                           "research/factory_throughput.py",
                           "benchmark": {"name": "EasyQuant LLM factor loop",
                                         "candidates_per_hour": EASYQUANT_PER_HOUR,
                                         "basis": "8 candidates per 15 min with auto-backtest "
                                                  "and walk-forward"},
                           "latency": lat}
    if not isinstance(rep, dict):
        doc["factory"] = {"status": UNMEASURED,
                          "why": f"{FACTORY_REPORT.name} absent or unreadable here"}
        doc["bottleneck"] = UNMEASURED
        return doc
    secs = float(rep.get("seconds") or 0.0)
    cells = rep.get("cells") or {}
    t0 = int((cells.get("tier0") or {}).get("evaluated") or 0)
    t1 = int((cells.get("tier1") or {}).get("evaluated") or 0)
    judge = int(cells.get("deferred_to_judge") or 0) + int(cells.get("survivors") or 0)
    per_h = (lambda n: round(n / secs * 3600)) if secs > 0 else (lambda n: None)
    stages = rep.get("stage_seconds")
    fac: dict[str, Any] = {
        "status": rep.get("status"), "report_at": rep.get("generated_at"),
        "dry_run": bool(rep.get("dry_run")), "pass_seconds": secs,
        "per_pass": {"generated": t0, "backtested_oos": t1, "queued_to_judge": judge},
        "per_compute_hour": {"generated": per_h(t0), "backtested_oos": per_h(t1),
                             "queued_to_judge": per_h(judge)},
        "vs_easyquant": ({"backtested_oos_per_pass_over_benchmark_hour":
                          round(t1 / EASYQUANT_PER_HOUR, 1)} if t1 else UNMEASURED),
        "stage_seconds": stages if isinstance(stages, dict) else UNMEASURED,
    }
    doc["factory"] = fac
    shares: dict[str, float] = {}
    if isinstance(stages, dict) and secs > 0:
        shares = {k: round(float(v) / secs, 3) for k, v in stages.items()}
        fac["stage_share"] = shares
    # THE WHOLE PATH'S BOTTLENECK: in-pass stages are seconds; the judge's queue is hours. When
    # the queued->verdict median exceeds the pass itself, the factory is not what binds.
    qv = ((lat.get("queued_to_verdict_h") or {}).get("p50") if lat.get("status") == "MEASURED"
          else None)
    waiting = (lat.get("awaiting_verdict") or {}) if lat.get("status") == "MEASURED" else {}
    if (qv is not None and secs > 0 and qv * 3600 > secs) or (waiting.get("n") or 0) > judge:
        doc["bottleneck"] = {"where": "judge queue (queued -> verdict)",
                             "queued_to_verdict_p50_h": qv,
                             "awaiting_verdict": waiting.get("n"),
                             "owner": "claude/sharded-judge-sweep (judge sharding)"}
    elif shares:
        top = max(shares, key=lambda k: shares[k])
        doc["bottleneck"] = {"where": f"factory stage {top}", "share_of_pass": shares[top]}
    else:
        doc["bottleneck"] = UNMEASURED
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.parse_args(argv)
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    fac = doc.get("factory") or {}
    print(f"factory_throughput: per compute hour {fac.get('per_compute_hour')}; "
          f"bottleneck {doc.get('bottleneck')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
