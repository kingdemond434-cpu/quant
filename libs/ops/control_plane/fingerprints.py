"""OPERATIONAL NEGATIVE KNOWLEDGE: a defect seen twice owes an invariant, not another fixer.

The desk keeps NEGATIVE KNOWLEDGE about strategies -- a failed family is published so no future
hour pays to rediscover it. It kept none about its own OPERATIONS, so the same breakages kept
arriving dressed as new ones, and each arrival grew a fresh healer instead of an impossibility.

The spec's own example: `shadow_spec.params = None` broke forward enrolment, was fixed, and broke
it again. The second occurrence is the signal. A shape that can arrive twice will arrive a third
time, and the repair for that is not a third fix -- it is a CONTRACT that makes the object
inadmissible, plus a test named against the fingerprint so the contract cannot quietly lapse.

A FINGERPRINT IS A NORMALISED DEFECT, not a traceback. Paths, line numbers, pids, hex addresses,
timestamps and quantities are stripped, so the same defect from two hosts, two runs and two line
numbers collapses to one row with a recurrence count. Rows live in
`desks/mt5/data/failure_fingerprints.jsonl` -- append-only, one json object per line, so a
corrupted tail costs the last row and never the history.

THE DEBT IS PUBLISHED, NEVER SILENT. `debt()` lists every fingerprint seen twice or more with no
invariant test named against it, and the reconciler carries that list into CONTROL_PLANE.json.
Naming the test is a deliberate act: `record(..., invariant_test="tests/ops/test_x.py::test_y")`.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
LEDGER = DESK / "data" / "failure_fingerprints.jsonl"

#: A fingerprint is RECURRENT at this count. Two is the number on purpose: once is an incident,
#: twice is a shape, and a shape is what an invariant can forbid.
RECURRENCE_THRESHOLD = 2

_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r'File "[^"]+", line \d+'), 'File "<path>", line <n>'),
    (re.compile(r"[A-Za-z]:[\\/][^\s'\"]+"), "<path>"),
    (re.compile(r"/(?:home|opt|usr|var|tmp)/[^\s'\"]+"), "<path>"),
    (re.compile(r"0x[0-9a-fA-F]+"), "<addr>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:[.+-][\d:]+)?\b"), "<ts>"),
    (re.compile(r"\bpid[= ]\d+\b", re.I), "pid=<n>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"\s+"), " "),
)


def normalise(text: str) -> str:
    """Strip everything that varies between two occurrences of the SAME defect."""
    out = str(text or "").strip()
    for pat, rep in _SUBS:
        out = pat.sub(rep, out)
    return out.strip()


def defect_class(text: str) -> str:
    """The exception type or the first token of the message -- the coarse bucket a human reads."""
    m = re.search(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning|Timeout))\b", str(text or ""))
    if m:
        return m.group(1)
    head = normalise(text).split(":", 1)[0].strip()
    return head[:60] or "UNCLASSIFIED"


def fingerprint(text: str, component_id: str | None = None) -> str:
    """The stable id of a defect shape. Component-scoped: the same TypeError in two organs is two
    problems, because the invariant that forbids it lives in two different contracts."""
    payload = f"{component_id or ''}|{normalise(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _rows(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or LEDGER
    out: list[dict[str, Any]] = []
    try:
        text = p.read_text(encoding="utf-8-sig")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def record(text: str, component_id: str | None = None, *, invariant_test: str | None = None,
           path: Path | None = None, **extra: Any) -> dict[str, Any]:
    """Append one occurrence. Returns the row, including its recurrence count so far.

    Never raises: telemetry that can take down the organ it observes gets deleted.
    """
    fp = fingerprint(text, component_id)
    prior = [r for r in _rows(path) if r.get("fingerprint") == fp]
    row: dict[str, Any] = {
        "fingerprint": fp,
        "component_id": component_id or "UNMEASURED",
        "defect_class": defect_class(text),
        "normalised": normalise(text)[:400],
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "occurrences": len(prior) + 1,
        "first_seen": (prior[0].get("first_seen") or prior[0].get("at")) if prior
        else datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "invariant_test": invariant_test or next(
            (str(r.get("invariant_test")) for r in reversed(prior) if r.get("invariant_test")),
            None),
    }
    if extra:
        row["extra"] = extra
    target = path or LEDGER
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
        row["written"] = True
    except OSError as exc:
        row["written"] = False
        row["why"] = f"{type(exc).__name__}: {exc}"
    return row


def census(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """fingerprint -> {occurrences, defect_class, component, first_seen, last_seen, test}."""
    out: dict[str, dict[str, Any]] = {}
    for r in _rows(path):
        fp = str(r.get("fingerprint") or "")
        if not fp:
            continue
        cur = out.setdefault(fp, {"fingerprint": fp, "occurrences": 0,
                                  "defect_class": r.get("defect_class"),
                                  "component_id": r.get("component_id"),
                                  "normalised": r.get("normalised"),
                                  "first_seen": r.get("first_seen") or r.get("at"),
                                  "last_seen": r.get("at"), "invariant_test": None})
        cur["occurrences"] += 1
        cur["last_seen"] = r.get("at") or cur["last_seen"]
        if r.get("invariant_test"):
            cur["invariant_test"] = str(r["invariant_test"])
    return out


def _test_exists(spec: str, root: Path | None = None) -> bool:
    """`tests/ops/test_x.py::test_y` -- the file must exist and, when a node id is given, the
    test function must be defined in it. A named test that does not exist is not an invariant."""
    base = root or ROOT
    file_part, _, node = str(spec).partition("::")
    p = base / file_part
    if not p.is_file():
        return False
    if not node:
        return True
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return re.search(rf"^\s*(?:async\s+)?def\s+{re.escape(node.split('[')[0])}\b", text,
                     re.M) is not None


def debt(path: Path | None = None, root: Path | None = None,
         threshold: int = RECURRENCE_THRESHOLD) -> list[dict[str, Any]]:
    """Every recurrent fingerprint with no LIVE invariant test named against it.

    This is the list the dashboard shows and the reconciler carries. It is deliberately not a
    gate: turning it red would mean a session that observes a second occurrence cannot commit
    until it has written the invariant, which is how an honest ledger acquires its first liar.
    """
    out: list[dict[str, Any]] = []
    for fp, row in sorted(census(path).items()):
        if int(row.get("occurrences") or 0) < threshold:
            continue
        test = row.get("invariant_test")
        if test and _test_exists(str(test), root):
            continue
        out.append({**row, "fingerprint": fp,
                    "owed": ("an invariant that makes this object inadmissible, plus a test "
                             "named against this fingerprint"),
                    "named_test": test, "named_test_exists": bool(test) and _test_exists(
                        str(test), root)})
    return out


def summary(path: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    c = census(path)
    d = debt(path, root)
    return {
        "fingerprints": len(c),
        "recurrent": sum(1 for r in c.values()
                         if int(r.get("occurrences") or 0) >= RECURRENCE_THRESHOLD),
        "debt": len(d),
        "debt_rows": d[:20],
        "rule": ("a fingerprint seen twice owes an invariant test named against it; until one "
                 "exists the debt is published"),
    }


def record_many(items: Iterable[Mapping[str, Any]], path: Path | None = None) -> int:
    n = 0
    for it in items:
        record(str(it.get("text") or ""), it.get("component_id"),
               invariant_test=it.get("invariant_test"), path=path)
        n += 1
    return n
