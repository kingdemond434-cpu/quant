"""Map every shared library organ to the MT5 desk by static reachability.

Static reachability proves wiring, not runtime operation or economic value. The
nightly controller uses the remaining set as a complete triage queue: wire and
test positive-EV venue-agnostic organs; explicitly block/archive incompatible
venue-specific ones; never manufacture usage merely to improve this metric.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path

VENUE_TOKENS = frozenset({
    "binance", "bybit", "deribit", "onchain", "wallet_graph",
    "crypto_source", "crypto_adapter", "multiexchange", "funding_caps",
})


def module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def resolve_local(name: str, known: set[str]) -> str | None:
    candidate = name
    while candidate:
        if candidate in known:
            return candidate
        candidate = candidate.rpartition(".")[0]
    return None


DISPOSITIONS_FILE = "docs/research/mt5_capability_dispositions.json"
_VALID_VERDICTS = frozenset({"SUPERSEDED", "BLOCKED"})
_MIN_REASON = 40  # a disposition with no substantive reason is a queue-shrink, not a decision


def load_dispositions(root: Path) -> tuple[dict[str, dict], list[str]]:
    """Recorded block/archive verdicts (2026-08-26). The audit demanded 'an explicit
    block/archive disposition' and provided nowhere to record one, so every weekly seat
    re-inspected the same modules. Invalid rows are returned separately and REPORTED --
    a malformed disposition must never silently shrink the queue."""
    try:
        raw = json.loads((root / DISPOSITIONS_FILE).read_text("utf-8"))
    except (OSError, ValueError):
        return {}, []
    good: dict[str, dict] = {}
    invalid: list[str] = []
    for module, row in (raw.get("dispositions") or {}).items():
        verdict = str(row.get("verdict", ""))
        reason = str(row.get("reason", ""))
        if verdict in _VALID_VERDICTS and len(reason) >= _MIN_REASON:
            good[module] = row
        else:
            invalid.append(module)
    return good, invalid


def audit(root: Path, *, now: datetime | None = None) -> dict:
    libs = sorted((root / "libs").rglob("*.py"))
    desk_files = sorted((root / "desks" / "mt5").rglob("*.py"))
    by_module = {module_name(root, path): path for path in libs}
    known = set(by_module)
    graph: dict[str, set[str]] = defaultdict(set)
    for name, path in by_module.items():
        for imported in imports(path):
            target = resolve_local(imported, known)
            if target:
                graph[name].add(target)

    roots: set[str] = set()
    consumers: dict[str, list[str]] = defaultdict(list)
    for path in desk_files:
        for imported in imports(path):
            target = resolve_local(imported, known)
            if target:
                roots.add(target)
                consumers[target].append(path.relative_to(root).as_posix())

    reachable = set(roots)
    queue = deque(sorted(roots))
    while queue:
        current = queue.popleft()
        for dependency in graph.get(current, set()):
            if dependency not in reachable:
                reachable.add(dependency)
                queue.append(dependency)

    rows = []
    # Package __init__ files are namespace plumbing, not economic organs. Keep
    # them in the dependency graph but exclude them from coverage counts so the
    # audit cannot inflate its backlog or its progress with package shells.
    reportable = {
        name for name, path in by_module.items() if path.name != "__init__.py"
    }
    dispositions, invalid_dispositions = load_dispositions(root)
    for name in sorted(reportable):
        path = by_module[name].relative_to(root).as_posix()
        venue_specific = any(token in name.lower() for token in VENUE_TOKENS)
        disposed = dispositions.get(name)
        if name in reachable:
            # Reachability outranks any verdict: a disposed module that gained a real
            # consumer reports REACHABLE, with the now-stale disposition flagged.
            status = "REACHABLE_MT5_STATIC"
        elif disposed:
            status = f"DISPOSED_{disposed['verdict']}"
        elif venue_specific:
            status = "VENUE_SPECIFIC_REVIEW"
        else:
            status = "UNWIRED_REVIEW"
        row = {
            "module": name,
            "path": path,
            "status": status,
            "direct_mt5_consumers": sorted(consumers.get(name, [])),
            "proof_level": "STATIC_REACHABILITY_ONLY",
        }
        if disposed:
            row["disposition"] = {**disposed, "stale": name in reachable}
        rows.append(row)

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["status"]] += 1
    if invalid_dispositions:
        counts["DISPOSITION_INVALID"] = len(invalid_dispositions)
    return {
        "schema_version": 1,
        "generated_at": (now or datetime.now(tz=UTC)).astimezone(UTC).isoformat(),
        "scope": "ALL_SHARED_LIBS_TO_MT5",
        "authority": "AUDIT_ONLY_NO_PROMOTION_NO_EXECUTION",
        "counts": dict(sorted(counts.items())),
        "rows": rows,
        "interpretation": (
            "REACHABLE_MT5_STATIC proves a code path only, never runtime or economic value. "
            "UNWIRED_REVIEW is the nightly positive-EV triage queue. VENUE_SPECIFIC_REVIEW "
            "requires an MT5-equivalence proof or an explicit block/archive disposition. "
            f"DISPOSED_* rows carry recorded verdicts from {DISPOSITIONS_FILE} (reachability "
            "outranks a verdict; DISPOSITION_INVALID counts malformed rows that were refused)."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output or root / "data" / "intelligence" / "mt5_capability_reuse.json"
    payload = audit(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), "utf-8")
    os.replace(tmp, output)
    print(json.dumps(payload["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
