#!/usr/bin/env python3
"""THE BUILD-FAILURE BANK -- every hypothesis or cell that failed to BUILD, by cause, as fix work.

A cell that never builds is never judged, and until now nothing counted why. Three stages drop
cells before any gate sees them, and each dropped them its own quiet way:

    run_external_backtest.run_cell   returned None on an unknown family, a symbol the registry
                                     does not carry, a raised family (the `except` printed one
                                     line into a log and moved on), or fewer than 20 signals;
                                     unresolvable family inputs were COUNTED in a local Counter
                                     that was never written anywhere
    miner_candidate_compiler         a compiled candidate missing its symbol, family, params or
                                     named mechanism was `continue`d past with only a tally
    external_gauntlet (sealed)       publishes its own NOT_RUN_BUILD_FAILED / NOT_RUN_DATA_MISSING
                                     / NOT_RUN_MODIFIER rows with a `why` -- read here, read-only;
                                     the judge itself is never edited

This is the one place the three meet. A stage records failures into a `Bank` while it runs and
flushes ONE summary row per pass (counts by cause class, a handful of examples per class) to
`desks/mt5/data/build_failures.jsonl`, so the ledger grows by a few rows an hour whatever the
docket size. The hourly leg `build_failure_bank` aggregates the window into
`desks/mt5/reports/BUILD_FAILURE_BANK.json`: cause classes ranked by count, each with its stage,
its share, examples and the owner the fix belongs to -- the top causes are the fix work.

UNMEASURED IS A VERDICT (L1.28a). A window in which no stage recorded a pass reads UNMEASURED
with its reason, never "zero failures".

RECORDING ONLY. Nothing here rejects, re-routes, retries or caps a cell. A recorder that can
throw would take down the stage it watches, so every write is guarded.

    python desks/mt5/research/build_failure_bank.py --once [--window-h 24]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data"
LEDGER = DATA / "build_failures.jsonl"
GAUNTLET_REPORT = DESK / "reports" / "universal_gates_external.json"
OUT = DESK / "reports" / "BUILD_FAILURE_BANK.json"

SCHEMA = "build-failure-bank/1"
UNMEASURED = "UNMEASURED"
#: Examples kept per cause class per pass. The counts are exact; the examples are for a reader.
MAX_EXAMPLES = 5
#: The ledger is trimmed to its newest half past this size; a summary row is ~2 KB.
MAX_LEDGER_BYTES = 8 * 1024 * 1024

#: The cause vocabulary, and who owns the fix for each. A cause outside it is still recorded
#: (as itself) so a new failure shape is never silenced; this table is where it gets an owner.
CAUSES: dict[str, str] = {
    "COMPILE_ERROR": "the family's own code raised while building signals (family author)",
    "MISSING_DATA": "the bars or an input series is absent on this host (data / refresh_bars)",
    "UNKNOWN_SYMBOL": "the symbol is not in the broker registry (universe / symbol mapping)",
    "UNKNOWN_FAMILY": "no implementation of the family on this host (family registry)",
    "INPUTS_UNRESOLVED": "peers, factors, swap or macro inputs could not be rebuilt "
                         "(mt5desk.family_inputs)",
    "INSUFFICIENT_SIGNALS": "the cell built but produced too few signals or trades to judge "
                            "(parameters / deepening)",
    "SPEC_INVALID": "the compiled spec is missing its symbol, family, params or a named "
                    "mechanism (miner_candidate_compiler / the producing seat)",
    "MODIFIER_REFUSED": "a cell modifier refused the spec before build (cell_modifiers)",
    "OTHER": "unclassified; read the examples and add a class",
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


def classify_exception(exc: BaseException) -> str:
    """Cause class for an exception raised while building a cell."""
    if isinstance(exc, (FileNotFoundError, OSError)):
        return "MISSING_DATA"
    text = f"{type(exc).__name__}: {exc}".lower()
    if isinstance(exc, KeyError) and ("column" in text or "bars" in text):
        return "MISSING_DATA"
    if "no such file" in text or "not found" in text or "missing" in text:
        return "MISSING_DATA"
    return "COMPILE_ERROR"


_WHY_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"not_run_modifier|modifier", re.I), "MODIFIER_REFUSED"),
    (re.compile(r"no implementation of family|unknown family", re.I), "UNKNOWN_FAMILY"),
    (re.compile(r"input load failed|inputs?\b.*(missing|unresolv|incomplete)|factor basket|"
                r"peer", re.I), "INPUTS_UNRESOLVED"),
    (re.compile(r"no \w+ bars|parquet missing|data missing|not_run_data_missing|no bars",
                re.I), "MISSING_DATA"),
    (re.compile(r"raised|error|exception", re.I), "COMPILE_ERROR"),
    (re.compile(r"no executable cell|too few|signals", re.I), "INSUFFICIENT_SIGNALS"),
)


def classify_why(why: str, status: str = "") -> str:
    """Cause class for a free-text reason (the sealed gauntlet's `why` / `downstream_status`)."""
    if status.upper() == "NOT_RUN_DATA_MISSING":
        return "MISSING_DATA"
    if status.upper() == "NOT_RUN_MODIFIER":
        return "MODIFIER_REFUSED"
    for rx, cause in _WHY_RULES:
        if rx.search(why or ""):
            return cause
    return "OTHER"


class Bank:
    """One stage's failures for one pass. `record` is cheap and never raises; `flush` writes one
    summary row and returns it (or None when there was nothing to write or the write failed)."""

    def __init__(self, stage: str, ledger: Path | None = None) -> None:
        self.stage = stage
        self.ledger = ledger or LEDGER
        self.counts: Counter[str] = Counter()
        self.by_family: dict[str, Counter[str]] = defaultdict(Counter)
        self.examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.attempted = 0
        self.started = _now()

    def attempt(self, n: int = 1) -> None:
        self.attempted += n

    def record(self, cause: str, detail: str = "", **ident: Any) -> None:
        try:
            cause = str(cause or "OTHER").upper()
            self.counts[cause] += 1
            fam = str(ident.get("family") or "?")
            self.by_family[cause][fam] += 1
            if len(self.examples[cause]) < MAX_EXAMPLES:
                ex = {k: (v if isinstance(v, (int, float, bool)) or v is None else str(v)[:120])
                      for k, v in ident.items()}
                ex["detail"] = str(detail or "")[:240]
                self.examples[cause].append(ex)
        except Exception:                                   # noqa: BLE001 - a recorder never raises
            pass

    def row(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA, "stage": self.stage,
            "started_at": self.started.isoformat(timespec="seconds"),
            "at": _now().isoformat(timespec="seconds"),
            "attempted": self.attempted,
            "failed": int(sum(self.counts.values())),
            "by_cause": dict(self.counts.most_common()),
            "by_cause_family": {c: dict(f.most_common(10)) for c, f in self.by_family.items()},
            "examples": {c: v for c, v in self.examples.items()},
        }

    def flush(self) -> dict[str, Any] | None:
        """Append this pass's summary. A pass that attempted cells and failed none is written
        too: zero failures over N attempts is a measurement, and its absence would read as
        UNMEASURED downstream."""
        if not self.attempted and not self.counts:
            return None
        row = self.row()
        try:
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
            _trim(self.ledger)
        except Exception as exc:                            # noqa: BLE001 - never breaks a build
            print(f"build_failure_bank: could not append {self.stage} pass to {self.ledger}: "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return None
        return row


def _trim(path: Path) -> None:
    try:
        if path.stat().st_size <= MAX_LEDGER_BYTES:
            return
        lines = path.read_text("utf-8").splitlines()
        path.write_text("\n".join(lines[len(lines) // 2:]) + "\n", "utf-8")
    except OSError:
        return


def _parse_ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def read_ledger(path: Path, since: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                t = _parse_ts(r.get("at")) if isinstance(r, dict) else None
                if t is not None and t >= since:
                    rows.append(r)
    except OSError:
        return []
    return rows


def gauntlet_row(path: Path, since: datetime) -> dict[str, Any] | None:
    """The sealed judge's own blocked-build verdicts, read-only, as one summary row."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    at = None
    for k in ("generated_at", "at", "built_utc", "measured_at", "ts"):
        at = _parse_ts(doc.get(k))
        if at:
            break
    if at is None:
        try:
            at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        except OSError:
            return None
    if at < since:
        return None
    bank = Bank("external_gauntlet", ledger=Path("/dev/null"))
    verdicts = [v for v in (doc.get("verdicts") or []) if isinstance(v, dict)]
    bank.attempt(len(verdicts))
    for v in verdicts:
        status = str(v.get("downstream_status") or "")
        if status not in ("NOT_RUN_BUILD_FAILED", "NOT_RUN_DATA_MISSING", "NOT_RUN_MODIFIER"):
            continue
        why = str(v.get("why") or status)
        bank.record(classify_why(why, status), why, symbol=v.get("sym"), family=v.get("family"),
                    status=status)
    row = bank.row()
    row["at"] = at.isoformat(timespec="seconds")
    row["source"] = str(path.relative_to(DESK.parent.parent)) if path.is_relative_to(
        DESK.parent.parent) else str(path)
    return row


def aggregate(rows: list[dict[str, Any]], window_h: float) -> dict[str, Any]:
    now = _now()
    doc: dict[str, Any] = {"schema": SCHEMA, "at": now.isoformat(timespec="seconds"),
                           "window_h": window_h, "ledger": "desks/mt5/data/build_failures.jsonl",
                           "causes_vocabulary": CAUSES}
    if not rows:
        doc.update({"status": UNMEASURED, "why": (
            "no stage recorded a build pass inside the window -- neither the backtest, the "
            "compiler nor the gauntlet's report; zero failures is NOT the reading"),
            "n_passes": 0, "fix_work": [], "stages": {}})
        return doc
    by_cause: Counter[str] = Counter()
    stage_cause: dict[str, Counter[str]] = defaultdict(Counter)
    fam: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stages: dict[str, dict[str, Any]] = {}
    for r in rows:
        st = str(r.get("stage") or "?")
        s = stages.setdefault(st, {"passes": 0, "attempted": 0, "failed": 0, "last_at": None})
        s["passes"] += 1
        s["attempted"] += int(r.get("attempted") or 0)
        s["failed"] += int(r.get("failed") or 0)
        if not s["last_at"] or str(r.get("at")) > str(s["last_at"]):
            s["last_at"] = r.get("at")
        for c, n in (r.get("by_cause") or {}).items():
            by_cause[c] += int(n)
            stage_cause[st][c] += int(n)
        for c, f in (r.get("by_cause_family") or {}).items():
            for k, n in (f or {}).items():
                fam[c][k] += int(n)
        for c, ex in (r.get("examples") or {}).items():
            for e in ex or []:
                if len(examples[c]) < MAX_EXAMPLES:
                    examples[c].append({**e, "stage": st})
    for s in stages.values():
        s["failure_rate"] = (round(s["failed"] / s["attempted"], 6) if s["attempted"]
                             else UNMEASURED)
    total = sum(by_cause.values())
    fix_work = []
    for rank, (c, n) in enumerate(by_cause.most_common(), start=1):
        fix_work.append({
            "rank": rank, "cause": c, "count": n,
            "share": round(n / total, 6) if total else 0.0,
            "owner": CAUSES.get(c, CAUSES["OTHER"]),
            "stages": dict(Counter({st: sc[c] for st, sc in stage_cause.items()
                                    if sc.get(c)}).most_common()),
            "top_families": dict(fam[c].most_common(8)),
            "examples": examples.get(c, []),
        })
    doc.update({
        "status": "MEASURED", "n_passes": len(rows), "n_failed": total,
        "n_attempted": sum(s["attempted"] for s in stages.values()),
        "stages": stages, "by_cause": dict(by_cause.most_common()), "fix_work": fix_work,
        "top_cause": fix_work[0]["cause"] if fix_work else None,
        "rule": ("recording only: nothing here rejects, retries or caps a cell. The top causes "
                 "are the fix work; each names the owner of the fix."),
    })
    return doc


def build(window_h: float = 24.0, ledger: Path | None = None,
          gauntlet: Path | None = None) -> dict[str, Any]:
    since = _now() - timedelta(hours=window_h)
    rows = read_ledger(ledger or LEDGER, since)
    g = gauntlet_row(gauntlet or GAUNTLET_REPORT, since)
    if g is not None:
        rows.append(g)
    return aggregate(rows, window_h)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--window-h", type=float, default=24.0)
    ap.add_argument("--budget-s", type=float, default=60.0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(a.window_h)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    tmp.replace(a.out)
    top = ", ".join(f"{w['cause']} {w['count']}" for w in doc.get("fix_work", [])[:4])
    print(f"build_failure_bank: {doc['status']} passes={doc.get('n_passes', 0)} "
          f"failed={doc.get('n_failed', 0)} top=[{top}] -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
