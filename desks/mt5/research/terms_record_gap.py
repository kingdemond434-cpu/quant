"""How many of the desk's fetches went to hosts whose terms it has not read: measured every pass.

THE DEFECT THIS MEASURES. LAWS 5e act 6 (amended 2026-11-17) refuses an automated fetch that a
host's robots.txt or terms refuse, and Governance ruled (2026-11-17 23:50Z) that act 6 is read
STRICTLY: terms the desk has not read refuse too. The desk's fetch paths do not yet consult a
reviewed-terms record, so every fetch to a host with no record in `libs/data/terms_records/`
is a fetch the law refuses. The refusal is reached in steps, and this organ is the measuring one:
it publishes the size of the gap each pass so it can be closed host by host, highest volume first.
It changes no fetch path; step 4 (refusing unrecorded hosts at the fetch) is NOT taken here.

THIS REPORT IS NOT A PERMISSION. A host listed here is not cleared by being listed, and a host
absent from it is not cleared by being absent. A host whose record says `forbids` or `unreadable`
and that still shows fetches is listed separately: that is the same defect, larger.

WHAT IS COUNTED (artifacts already on disk; nothing is fetched):

* `data/intelligence/world/frontier.json` -- the world crawler's per-URL `fetches` counter
  (a real HTTP fetch count; unit `fetch`).
* `data/intelligence/blocked_sources.json` -- seed miners' per-platform `attempts` (unit
  `attempt`).
* `data/deep_forest_claims.jsonl`, `data/deep_forest_datasets.jsonl`, `data/mined_sources.jsonl`,
  `data/news_captures.jsonl` -- documents captured by the deep-forest miner, the provenance ledger
  and the news lane, counted as DISTINCT URLs per host (unit `captured_url`), since a page that
  yielded five claims was fetched once.

The units differ, so the per-host figure is called `observations` and every row keeps its
per-input breakdown. Collectors that keep no per-host record on disk (polite_fetch's STATS are
per leg and in memory) are not counted, and the report names that as a coverage gap rather than
reading it as zero. AN ABSENT OR UNREADABLE INPUT IS UNMEASURED, NEVER ZERO; an unreadable terms
registry makes every recorded/unrecorded figure UNMEASURED.

Outputs: `reports/TERMS_RECORD_GAP.json` (the gap) and `reports/TERMS_BACKFILL_QUEUE.json` (the
unrecorded hosts ranked by observations, then by how many inputs saw them, then by name -- the
order a later session reads their terms in).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_records as tr  # noqa: E402

REPORT = DESK / "reports" / "TERMS_RECORD_GAP.json"
QUEUE = DESK / "reports" / "TERMS_BACKFILL_QUEUE.json"
UNMEASURED = "UNMEASURED"
TOP_N = 25
LAW = ("DEFECT AGAINST LAWS 5e act 6 (Governance ruling 2026-11-17 23:50Z): act 6 is read "
       "strictly, so a host whose terms the desk has not read is refused; every fetch counted "
       "under to_unrecorded_hosts went to such a host.")
NOT_A_PERMISSION = ("This report is NOT a permission. Listing a host does not clear it, absence "
                    "from the list does not clear a host, and the fetch paths are unchanged: "
                    "step 4 (refusing unrecorded hosts at the fetch) is not yet taken.")
UNCOUNTED = ("collectors that keep no per-host fetch record on disk (alt_proxies, keyed_sources, "
             "free_stack, index_discovery, live feeds: polite_fetch STATS are per leg and in "
             "memory) are not in these counts; their volume is UNMEASURED, not zero")


def _counter_frontier(doc: Any) -> Counter[str]:
    out: Counter[str] = Counter()
    for url, row in (doc.get("sources") or {}).items():
        if not isinstance(row, Mapping):
            continue
        key = tr.record_key(str(row.get("host") or url))
        n = row.get("fetches")
        if key and isinstance(n, int) and n > 0:
            out[key] += n
    return out


def _counter_attempts(doc: Any) -> Counter[str]:
    out: Counter[str] = Counter()
    for row in (doc.get("sources") or {}).values():
        if not isinstance(row, Mapping):
            continue
        key = tr.record_key(str(row.get("url") or ""))
        n = row.get("attempts")
        if key and isinstance(n, int) and n > 0:
            out[key] += n
    return out


def _counter_distinct_urls(rows: Iterable[Any]) -> Counter[str]:
    seen: set[str] = set()
    out: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        url = str(row.get("url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        key = tr.record_key(url)
        if key:
            out[key] += 1
    return out


def _read_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _read_jsonl(p: Path) -> list[Any]:
    rows: list[Any] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


#: (name, path under the desk, unit, reader, counter)
INPUTS: tuple[tuple[str, str, str, Callable[[Path], Any], Callable[[Any], Counter[str]]], ...] = (
    ("world_frontier", "data/intelligence/world/frontier.json", "fetch", _read_json,
     _counter_frontier),
    ("blocked_sources", "data/intelligence/blocked_sources.json", "attempt", _read_json,
     _counter_attempts),
    ("deep_forest_claims", "data/deep_forest_claims.jsonl", "captured_url", _read_jsonl,
     _counter_distinct_urls),
    ("deep_forest_datasets", "data/deep_forest_datasets.jsonl", "captured_url", _read_jsonl,
     _counter_distinct_urls),
    ("mined_sources", "data/mined_sources.jsonl", "captured_url", _read_jsonl,
     _counter_distinct_urls),
    ("news_captures", "data/news_captures.jsonl", "captured_url", _read_jsonl,
     _counter_distinct_urls),
)


def measure_inputs(desk: Path = DESK) -> list[dict[str, Any]]:
    """Each input with its per-host counts, or UNMEASURED with the reason."""
    out: list[dict[str, Any]] = []
    for name, rel, unit, reader, counter in INPUTS:
        p = desk / rel
        row: dict[str, Any] = {"name": name, "path": f"desks/mt5/{rel}", "unit": unit}
        if not p.exists():
            out.append({**row, "status": UNMEASURED, "why": "absent", "counts": None})
            continue
        try:
            counts = counter(reader(p))
            st = p.stat()
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            out.append({**row, "status": UNMEASURED,
                        "why": f"unreadable: {type(exc).__name__}", "counts": None})
            continue
        out.append({**row, "status": "MEASURED", "counts": counts,
                    "observations": sum(counts.values()), "hosts": len(counts),
                    "mtime": datetime.fromtimestamp(st.st_mtime, UTC).isoformat(
                        timespec="seconds")})
    return out


def rank_queue(per_host: Mapping[str, Mapping[str, int]],
               recorded: Callable[[str], str | None]) -> list[dict[str, Any]]:
    """Unrecorded hosts, ranked: observations desc, inputs that saw it desc, host asc."""
    rows = []
    for host, by_input in per_host.items():
        if recorded(host) is not None:
            continue
        rows.append({"host": host, "observations": sum(by_input.values()),
                     "n_inputs": len(by_input), "by_input": dict(sorted(by_input.items()))})
    rows.sort(key=lambda r: (-r["observations"], -r["n_inputs"], r["host"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def registry_freshness(registry: Path | None = None) -> dict[str, Any]:
    """Whether the committed registry still equals what the held evidence seeds
    (`scripts/seed_terms_records.py`). STALE means a session added or changed terms evidence in
    the code without re-seeding, so a reading the desk holds is missing from the record."""
    try:
        from scripts import seed_terms_records as seed
        fresh = seed.build()["records"]
        held = tr.load(registry)
    except Exception as exc:                       # reported, never raised
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:300]}
    added = sorted(set(fresh) - set(held))
    changed = sorted(k for k in set(fresh) & set(held) if fresh[k] != held[k])
    return {"status": "STALE" if added or changed else "CURRENT",
            "hosts_held_but_unrecorded": added, "hosts_changed": changed,
            "fix": "python scripts/seed_terms_records.py" if added or changed else None}


def build(desk: Path = DESK, registry: Path | None = None,
          previous: Mapping[str, Any] | None = None,
          now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """(gap report, backfill queue). Pure apart from reading the named files."""
    at = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    inputs = measure_inputs(desk)
    measured = [i for i in inputs if i["status"] == "MEASURED"]
    reg: dict[str, Any] = {"path": "libs/data/terms_records/"}
    records: dict[str, dict[str, Any]] | None
    try:
        records = tr.load(registry)
        reg.update(status="READ", records=len(records))
    except tr.TermsRecordsUnreadable as exc:
        records = None
        reg.update(status=UNMEASURED, why=f"registry unreadable (fail closed): {exc}"[:400])

    per_host: dict[str, dict[str, int]] = {}
    for i in measured:
        for host, n in i["counts"].items():
            per_host.setdefault(host, {})[i["name"]] = n
    total = sum(sum(v.values()) for v in per_host.values())

    def recorded(host: str) -> str | None:
        return tr.matching_key(host, records.keys()) if records is not None else None

    base: dict[str, Any] = {
        "schema": "terms_record_gap/1", "generated_at": at,
        "law": LAW, "not_a_permission": NOT_A_PERMISSION,
        "registry": reg,
        "inputs": [{k: v for k, v in i.items() if k != "counts"} for i in inputs],
        "coverage_gap": UNCOUNTED,
        "missed_growth": None,
        "missed_growth_note": ("none: this organ holds, cuts and refuses nothing; it measures. "
                               "The hold that act 6 requires lands in step 4, which carries "
                               "its own missed_growth line."),
    }
    if not measured or records is None:
        why = ("no input could be read" if not measured
               else "the terms registry is unreadable, so recorded vs unrecorded is unknown")
        report = {**base, "status": UNMEASURED, "why": why,
                  "totals": {"observations": total if measured else UNMEASURED,
                             "to_unrecorded_hosts": UNMEASURED,
                             "unrecorded_share": UNMEASURED},
                  "top_unrecorded": UNMEASURED, "fetched_despite_refusing_record": UNMEASURED,
                  "since_last_pass": UNMEASURED,
                  "defect": f"{LAW} Size: UNMEASURED ({why})."}
        queue = {"schema": "terms_backfill_queue/1", "generated_at": at, "status": UNMEASURED,
                 "why": why, "sources": base["inputs"], "queue": []}
        return report, queue

    by_verdict: Counter[str] = Counter()
    refusing: list[dict[str, Any]] = []
    for host, by_input in per_host.items():
        k = recorded(host)
        n = sum(by_input.values())
        if k is None:
            by_verdict["unrecorded"] += n
            continue
        v = records[k]["verdict"]
        by_verdict[v] += n
        if v != "permits":
            refusing.append({"host": host, "record": k, "verdict": v, "observations": n,
                             "by_input": dict(sorted(by_input.items()))})
    refusing.sort(key=lambda r: (-r["observations"], r["host"]))
    ranked = rank_queue(per_host, recorded)
    unrec = by_verdict["unrecorded"]
    totals = {"observations": total, "to_unrecorded_hosts": unrec,
              "unrecorded_share": round(unrec / total, 4) if total else UNMEASURED,
              "to_permits": by_verdict["permits"], "to_forbids": by_verdict["forbids"],
              "to_unreadable": by_verdict["unreadable"],
              "hosts": len(per_host), "unrecorded_hosts": len(ranked),
              "inputs_measured": len(measured), "inputs_total": len(inputs)}
    since: Any = UNMEASURED
    prev_t = (previous or {}).get("totals") if isinstance(previous, Mapping) else None
    if isinstance(prev_t, Mapping) and all(isinstance(prev_t.get(f), int) for f in
                                           ("observations", "to_unrecorded_hosts")) \
            and prev_t.get("inputs_measured") == len(measured):
        since = {"previous_at": previous.get("generated_at") if previous else None,
                 "observations": total - prev_t["observations"],
                 "to_unrecorded_hosts": unrec - prev_t["to_unrecorded_hosts"]}
    status = "DEFECT" if unrec or refusing else "NO_UNRECORDED_FETCH_ON_MEASURED_INPUTS"
    report = {
        **base, "status": status, "totals": totals,
        "defect": (f"{LAW} Measured size: {unrec} of {total} observations "
                   f"({totals['unrecorded_share']}) on {len(ranked)} unrecorded host(s), across "
                   f"{len(measured)} of {len(inputs)} inputs; plus "
                   f"{sum(r['observations'] for r in refusing)} observations on "
                   f"{len(refusing)} host(s) whose record forbids or is unreadable."),
        "top_unrecorded": [{k: r[k] for k in ("rank", "host", "observations", "by_input")}
                           for r in ranked[:TOP_N]],
        "fetched_despite_refusing_record": refusing,
        "since_last_pass": since,
    }
    queue = {"schema": "terms_backfill_queue/1", "generated_at": at, "status": "MEASURED",
             "doc": ("Hosts the desk fetched or captured from with no reviewed-terms record, "
                     "ranked by observations (desc), then number of inputs (desc), then host. A "
                     "later session reads each host's terms and adds its record to "
                     "its group file in libs/data/terms_records/ (URL, date, verbatim "
                     "clause). NOT a permission."),
             "ranking": "observations desc, n_inputs desc, host asc",
             "sources": base["inputs"], "coverage_gap": UNCOUNTED,
             "n_hosts": len(ranked), "queue": ranked}
    return report, queue


def _write(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--out", type=Path, default=REPORT)
    ap.add_argument("--queue-out", type=Path, default=QUEUE)
    args = ap.parse_args(argv)
    try:
        previous = json.loads(args.out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    report, queue = build(previous=previous)
    report["registry"]["freshness"] = registry_freshness()
    _write(args.out, report)
    _write(args.queue_out, queue)
    t = report["totals"]
    print(f"terms_record_gap: {report['status']} to_unrecorded={t['to_unrecorded_hosts']} "
          f"of {t['observations']}; queue={len(queue['queue'])} hosts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
