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

THE TERMINAL STAMP (2026-10-20). `rejections_by_terminal_gate` folded every row with no gate into
one UNKNOWN bucket: 587,075 of 963,604 on 10-20, which blinded the mutation arms. The judge now
stamps every row with `terminal_kind` / `terminal_gate_id` / `terminal_reason`
(`external_gauntlet.terminal_stamp`), and this digest reads that stamp -- deriving it by the same
rule for a row written before the stamp existed -- into `by_terminal_kind`,
`rejections_by_terminal_gate_id` (RULED rows only), `unmeasured_by_reason`, `not_run_by_status`
and `terminal_defects`. A row no rule can name is a DEFECT: counted, sampled and surfaced in
the top-level `terminal_defects`, never folded into a silent UNKNOWN. The old keys are kept
verbatim for every existing reader.

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
DEFECT_SAMPLE = 20

#: The judge's own vocabulary (`external_gauntlet.TERMINAL_KINDS`), copied because the judge is
#: sealed and heavy to import; `test_gate_verdict_digest` pins the two equal.
TERMINAL_KINDS = ("PASSED", "RULED", "UNMEASURED", "NOT_RUN", "DEFECT")
TERMINAL_DEFECT = "no_terminal_gate_recorded"


def terminal_of(r: dict[str, Any]) -> tuple[str, str, str]:
    """(kind, gate id, reason) for one ledger row or sweep verdict; never an empty gate id.

    A stamped row is read as stamped. An unstamped row is classified by the judge's rule: passed
    -> PASSED; never built (`passed` null, NOT_RUN_* status) -> NOT_RUN; the unmeasured branch
    (an `unknown_reason`, or `unmeasured`) -> UNMEASURED at gate `observations`; a named gate ->
    RULED; a failed stage -> RULED at the first; anything else -> DEFECT. A ledger row from
    before 2026-09-30 that reads UNKNOWN with no reason is therefore a DEFECT, by name."""
    kind = str(r.get("terminal_kind") or "")
    gid = str(r.get("terminal_gate_id") or "")
    if kind in TERMINAL_KINDS and gid:
        return kind, gid, str(r.get("terminal_reason") or gid)[:REASON_CHARS]
    passed = r.get("passed")
    gate = str(r.get("terminal_gate") or "")
    status = str(r.get("downstream_status") or "")
    if passed is True:
        return "PASSED", "PASSED", "passed every gate"
    if passed is None and status.startswith("NOT_RUN"):
        return "NOT_RUN", status, str(r.get("why") or status)[:REASON_CHARS]
    if r.get("unmeasured") or r.get("unknown_reason"):
        return ("UNMEASURED", "observations",
                str(r.get("unknown_reason") or "observations_under_60_days")[:REASON_CHARS])
    if gate and gate.upper() not in ("UNKNOWN", "PASSED", "NONE"):
        return "RULED", gate, (_reason((r.get("stages") or {}).get(gate)
                                       if isinstance(r.get("stages"), dict) else None)
                               or gate)
    raw = r.get("stages")
    stages: dict[str, Any] = raw if isinstance(raw, dict) else {}
    failed = [k for k, s in stages.items() if isinstance(s, dict) and s.get("passed") is False]
    if passed is False and failed:
        return "RULED", str(failed[0]), _reason(stages[failed[0]]) or str(failed[0])
    return "DEFECT", TERMINAL_DEFECT, (f"{TERMINAL_DEFECT}: passed={passed!r}, "
                                       f"terminal_gate={gate or None!r}, "
                                       f"downstream_status={status or None!r}")


class _Terminal:
    """The stamp's counters, shared by the ledger and the sweep digests."""

    def __init__(self) -> None:
        self.kinds: Counter[str] = Counter()
        self.ruled: Counter[str] = Counter()
        self.unmeasured: Counter[str] = Counter()
        self.not_run: Counter[str] = Counter()
        self.defects = 0
        self.defects_stamped = 0
        self.stamped = 0
        self.defect_sample: list[dict[str, Any]] = []

    def add(self, r: dict[str, Any]) -> None:
        kind, gid, why = terminal_of(r)
        self.kinds[kind] += 1
        stamped = bool(r.get("terminal_kind") in TERMINAL_KINDS and r.get("terminal_gate_id"))
        self.stamped += stamped
        if kind == "RULED":
            self.ruled[gid] += 1
        elif kind == "UNMEASURED":
            self.unmeasured[why] += 1
        elif kind == "NOT_RUN":
            self.not_run[gid] += 1
        elif kind == "DEFECT":
            self.defects += 1
            self.defects_stamped += stamped
            if len(self.defect_sample) < DEFECT_SAMPLE:
                self.defect_sample.append({k: r.get(k) for k in ("at", "cell", "family",
                                                                  "terminal_gate", "passed",
                                                                  "downstream_status")})

    def doc(self) -> dict[str, Any]:
        return {
            "by_terminal_kind": dict(self.kinds.most_common()),
            "rows_carrying_the_stamp": self.stamped,
            "rejections_by_terminal_gate_id": dict(self.ruled.most_common()),
            "unmeasured_by_reason": dict(self.unmeasured.most_common()),
            "not_run_by_status": dict(self.not_run.most_common()),
            "terminal_defects": {"n": self.defects,
                                 "stamped_by_the_judge": self.defects_stamped,
                                 "derived_from_unstamped_rows": self.defects - self.defects_stamped,
                                 "sample": self.defect_sample,
                                 "rule": "a row no rule can name; a DEFECT, never UNKNOWN"},
        }


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
    term = _Terminal()
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
                                                      "downstream_status", "terminal_kind",
                                                      "terminal_gate_id")})
                term.add(r)
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
        **term.doc(),
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
    term = _Terminal()
    n_pass = 0
    for v in verdicts:
        term.add(v)
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
        **term.doc(),
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
        # AN UNNAMED TERMINAL GATE IS A NAMED DEFECT: the newest sweep's count, the ledger's, and
        # whether the newest sweep already carries the judge's stamp (UNMEASURED when unread).
        "terminal_defects": _defects_headline(led, swp),
    }


def _defects_headline(led: dict[str, Any], swp: dict[str, Any]) -> dict[str, Any]:
    """DEFECT when the newest sweep holds an unnamed row or the judge STAMPED one into the ledger.

    Ledger rows written before the stamp existed (UNKNOWN with no reason, 2026-09-12..30) are
    counted by name as `ledger_legacy` and never clear; they do not hold the status at DEFECT,
    because nothing a sweep does now can rename them."""
    out: dict[str, Any] = {}
    for name, d in (("ledger", led), ("latest_sweep", swp)):
        td = d.get("terminal_defects")
        out[name] = td.get("n") if isinstance(td, dict) else "UNMEASURED"
        if name == "ledger" and isinstance(td, dict):
            out["ledger_stamped"] = td.get("stamped_by_the_judge")
            out["ledger_legacy"] = td.get("derived_from_unstamped_rows")
    v = swp.get("verdicts")
    out["latest_sweep_stamped"] = (
        "UNMEASURED" if not isinstance(v, int) else
        bool(v) and swp.get("rows_carrying_the_stamp") == v)
    out["status"] = ("UNMEASURED" if "UNMEASURED" in (out["ledger"], out["latest_sweep"])
                     else "DEFECT" if (out.get("ledger_stamped") or out["latest_sweep"])
                     else "CLEAN")
    return out


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
