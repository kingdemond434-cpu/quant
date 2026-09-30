"""WHY CELLS DIE, IN A FILE SMALL ENOUGH TO COMMIT (2026-09-30).

The gauntlet already records which gate killed which cell: `external_gauntlet._append_gate_ledger`
appends to `desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl` once per change of mind, and every
sweep overwrites `desks/mt5/reports/universal_gates_external.json` with the full verdicts and their
per-stage messages. Both are gitignored -- the ledger grows without bound and the sweep report is
tens of megabytes -- so every reader off the box (the CRO cycle, the six-event trace, the audits)
has had to write "gate reasons: not committed". Measured 2026-09-30: the newest committed REJECT
with a gate named is 2026-09-12, in QQUANT_GATES.json, while the box judges every hour.

Un-ignoring either file would put a data lake on the wire. This writes the DIGEST instead:

    desks/mt5/reports/GATE_VERDICT_DIGEST.json
      ledger        per-gate rejection counts, per family x gate, per symbol (top), the window
      latest_sweep  the newest sweep's terminal gates, every gate's any-fail count, and up to
                    three distinct stage messages per gate -- the REASONS, verbatim, truncated
      latest        the newest N ledger rows (cell, family, gate, passed, at)

Bounded by construction (top-K everywhere, messages truncated), regenerated every hour by the
`publish_state` leg immediately before the box publishes, and carried by `sync_shadow_to_git.ps1`
in `$relPaths`. An absent input is UNMEASURED in the digest, never an empty count (L1.28a).
It reads; it judges nothing and moves no gate.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SWEEP = BASE / "reports" / "universal_gates_external.json"
OUT = BASE / "reports" / "GATE_VERDICT_DIGEST.json"

LATEST_N = 50
TOP_FAMILIES = 60
TOP_SYMBOLS = 40
REASONS_PER_GATE = 3
REASON_CHARS = 200


def _source(path: Path) -> dict[str, Any]:
    try:
        st = path.stat()
    except OSError:
        return {"path": path.relative_to(BASE.parent.parent).as_posix()
                if path.is_relative_to(BASE.parent.parent) else str(path),
                "status": "UNMEASURED", "why": "absent on this host"}
    return {"path": path.relative_to(BASE.parent.parent).as_posix()
            if path.is_relative_to(BASE.parent.parent) else str(path),
            "status": "READ", "bytes": st.st_size,
            "modified_at": datetime.fromtimestamp(st.st_mtime, UTC).isoformat(timespec="seconds")}


def digest_ledger(path: Path = LEDGER, latest_n: int = LATEST_N) -> dict[str, Any]:
    """Stream the append-only ledger once; counts plus the newest rows."""
    src = _source(path)
    if src["status"] != "READ":
        return {"source": src}
    per_gate: Counter[str] = Counter()
    per_family: dict[str, Counter[str]] = defaultdict(Counter)
    per_symbol: Counter[str] = Counter()
    latest: deque[dict[str, Any]] = deque(maxlen=max(0, latest_n))
    rows = passed = bad = 0
    first_at = last_at = None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                if not isinstance(r, dict):
                    bad += 1
                    continue
                rows += 1
                at = r.get("at")
                if at:
                    first_at = first_at or at
                    last_at = at
                latest.append({k: r.get(k) for k in ("at", "cell", "family", "sym",
                                                      "terminal_gate", "passed",
                                                      "downstream_status")})
                if r.get("passed"):
                    passed += 1
                    continue
                gate = str(r.get("terminal_gate") or "UNKNOWN")
                per_gate[gate] += 1
                per_family[str(r.get("family") or "UNKNOWN")][gate] += 1
                per_symbol[str(r.get("sym") or "UNKNOWN")] += 1
    except OSError as exc:
        return {"source": {**src, "status": "UNREADABLE", "why": str(exc)[:160]}}
    fams = sorted(per_family.items(), key=lambda kv: -sum(kv[1].values()))
    return {
        "source": src,
        "rows": rows, "malformed_rows": bad, "passed_rows": passed,
        "rejected_rows": rows - passed, "first_at": first_at, "last_at": last_at,
        "note": ("the ledger appends a row only when a cell's verdict CHANGES, so these count "
                 "changes of mind, not judgements"),
        "rejections_by_terminal_gate": dict(per_gate.most_common()),
        "rejections_by_family": {f: dict(c.most_common()) for f, c in fams[:TOP_FAMILIES]},
        "families_omitted": max(0, len(fams) - TOP_FAMILIES),
        "rejections_by_symbol_top": dict(per_symbol.most_common(TOP_SYMBOLS)),
        "latest": list(reversed(latest)),
    }


def _reason(stage: Any) -> str | None:
    if not isinstance(stage, dict):
        return None
    for key in ("message", "reason", "why", "detail"):
        v = stage.get(key)
        if v:
            return str(v)[:REASON_CHARS]
    keys = [k for k in ("value", "threshold", "stat", "p_value", "n") if k in stage]
    if keys:
        return ", ".join(f"{k}={stage[k]}" for k in keys)[:REASON_CHARS]
    return None


def digest_sweep(path: Path = SWEEP) -> dict[str, Any]:
    """The newest sweep: where cells stopped, which gates refused them, and what the gates said."""
    src = _source(path)
    if src["status"] != "READ":
        return {"source": src}
    try:
        doc = json.loads(path.read_text("utf-8", errors="replace"))
    except (OSError, ValueError) as exc:
        return {"source": {**src, "status": "UNREADABLE", "why": str(exc)[:160]}}
    verdicts = [v for v in (doc.get("verdicts") or []) if isinstance(v, dict)] \
        if isinstance(doc, dict) else []
    terminal: Counter[str] = Counter()
    any_fail: Counter[str] = Counter()
    fam_terminal: dict[str, Counter[str]] = defaultdict(Counter)
    reasons: dict[str, list[str]] = defaultdict(list)
    n_pass = 0
    for v in verdicts:
        if v.get("passed"):
            n_pass += 1
            continue
        gate = str(v.get("terminal_gate") or "UNKNOWN")
        terminal[gate] += 1
        fam_terminal[str(v.get("family") or "UNKNOWN")][gate] += 1
        stages = v.get("stages") if isinstance(v.get("stages"), dict) else {}
        failed = v.get("failed_gates") or [k for k, s in stages.items()
                                            if isinstance(s, dict) and not s.get("passed")]
        for g in failed:
            any_fail[str(g)] += 1
            why = _reason(stages.get(g))
            bucket = reasons[str(g)]
            if why and why not in bucket and len(bucket) < REASONS_PER_GATE:
                bucket.append(why)
    fams = sorted(fam_terminal.items(), key=lambda kv: -sum(kv[1].values()))
    stamp = None
    if isinstance(doc, dict):
        stamp = doc.get("swept_at") or doc.get("generated_at") or doc.get("timestamp")
    return {
        "source": src, "swept_at": stamp, "verdicts": len(verdicts), "passed": n_pass,
        "rejected": len(verdicts) - n_pass,
        "terminal_gates": dict(terminal.most_common()),
        "any_fail_by_gate": dict(any_fail.most_common()),
        "terminal_gates_by_family": {f: dict(c.most_common()) for f, c in fams[:TOP_FAMILIES]},
        "families_omitted": max(0, len(fams) - TOP_FAMILIES),
        "reasons_by_gate": dict(reasons),
        "n_curable_by_forward": sum(1 for v in verdicts if v.get("curable_by_forward")),
    }


def build(ledger: Path = LEDGER, sweep: Path = SWEEP, *, latest_n: int = LATEST_N,
          now: datetime | None = None) -> dict[str, Any]:
    led = digest_ledger(ledger, latest_n)
    swp = digest_sweep(sweep)
    measured = [k for k, d in (("ledger", led), ("latest_sweep", swp))
                if (d.get("source") or {}).get("status") == "READ"]
    return {
        "schema": "gate_verdict_digest/1",
        "generated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "status": "MEASURED" if len(measured) == 2 else ("PARTIAL" if measured
                                                         else "UNMEASURED"),
        "producer": "desks/mt5/research/gate_verdict_digest.py (hourly, publish_state leg)",
        "ledger": led,
        "latest_sweep": swp,
    }


def write(doc: dict[str, Any], out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        from libs.ops.win_write import replace_resilient
        replace_resilient(tmp, out)
    except ImportError:
        tmp.replace(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--latest", type=int, default=LATEST_N)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = build(latest_n=args.latest)
    path = write(doc, args.out)
    led, swp = doc["ledger"], doc["latest_sweep"]
    print(f"gate verdict digest: {doc['status']} -> {path.name}; ledger rows "
          f"{led.get('rows', 'UNMEASURED')}, sweep verdicts {swp.get('verdicts', 'UNMEASURED')}")
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE.parent.parent))
    raise SystemExit(main())
