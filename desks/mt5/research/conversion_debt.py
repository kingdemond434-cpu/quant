#!/usr/bin/env python3
"""CONVERSION DEBT -- what every unconverted mined row NEEDS, and the miner that is sent for it.

THE ASK (principal, 2026-10-09..13, ownership row N3): a 24/7 conversion organ that turns raw
rows, claims and text into exact executable cells, carries NEEDS_DATA / NEEDS_RULE / NEEDS_PIT
debt THAT DRIVES THE MINERS, and scales conversion instead of stopping discovery.

WHAT ALREADY EXISTED, AND WHAT DID NOT (measured 2026-11-10). The conversion itself is live:
`miner_candidate_compiler` compiles every row, `local_converter` and `deepening_worker` recover
rules, `conversion_maximiser` drains the registry's residue. Each of them NAMES why a row did not
convert. What none of them did is close the loop on the largest named class. The deepening worker
refuses a row whose miner captured a link and no page as REFUSED_NO_BODY_CAPTURED, with the remedy
written beside it -- "re-fetch the page body -- this is a COLLECTOR defect" -- and that remedy
was a sentence in a ledger. No collector read it. Measured by that organ: 59% of its backlog.

THE THREE CLASSES, each read from a label an organ already wrote (nothing is re-judged here):

    NEEDS_DATA   the row has nothing to read: the compiler's EMPTY_CAPTURE, the deepening
                 worker's REFUSED_NO_BODY_CAPTURED. The remedy is a FETCH.
    NEEDS_RULE   the row has text and no executable rule or no instrument was recovered from it:
                 NEEDS_EXACT_RULE_EXTRACTION, NEEDS_SYMBOL_EXTRACTION, and every worked row that
                 ended without a candidate and without a terminal refusal. The remedy is a READER.
    NEEDS_PIT    the row is in debt AND no producer stamped when it was retrieved: its only time
                 is the artifact's mtime (`retrieved_at_basis: artifact_mtime`) or nothing. A cell
                 minted from it could not be placed point-in-time. The remedy is a vaulted fetch.

A converted row, an OPERATIONAL_ROW and a BANNED_FAMILY refusal owe nothing and are counted as
such. A row whose label this module does not know is UNCLASSIFIED and counted, never dropped.

HOW THE DEBT DRIVES A MINER. Every NEEDS_DATA or NEEDS_PIT row with an http(s) address is offered
to the world crawler as a recapture seed (`data/hypotheses/conversion_debt_seeds.json`, read by
`world_crawler.conversion_debt_seeds`). The crawler owns the fetch budget, the per-host gap, the
point-in-time vault and the terms label, so this adds NO fetch path: it adds addresses to the
frontier the crawler already works, and ONLY on hosts that frontier already holds. A row on a
host the crawler does not work is published as UNROUTED with its host, and is not fetched. A row
with no address is owed by the miner that produced it, by name. NEEDS_RULE is already driven: the
deepening worker drains that queue hourly, and its backlog artifact is read here for the depth.

A RECAPTURE IS MEASURED, NOT ASSUMED. A seed counts as RECAPTURED only when the frontier shows a
fetch of that address at or after the row entered debt. Offered and not yet fetched is PENDING.
A frontier this host cannot read is UNMEASURED and no seed is offered (L1.28a).

WHAT IT NEVER DOES. It fetches nothing, judges nothing, mints no cell, and removes no row from
any queue. The gauntlet remains the only arbiter.

    python desks/mt5/research/conversion_debt.py [--dry-run] [--budget-s N]
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent

QUEUE = BASE / "data" / "hypotheses" / "miner_deepening_queue.json"
WORKED = BASE / "data" / "hypotheses" / "deepening_worked.jsonl"
BACKLOG = BASE / "reports" / "DEEPENING_BACKLOG.json"
FRONTIER = BASE / "data" / "intelligence" / "world" / "frontier.json"
SEEDS = BASE / "data" / "hypotheses" / "conversion_debt_seeds.json"
OUT = BASE / "reports" / "CONVERSION_DEBT.json"

CLASSES: tuple[str, ...] = ("NEEDS_DATA", "NEEDS_RULE", "NEEDS_PIT")

#: The compiler's disposition on a queued row -> the class it owes. Read, never re-derived.
QUEUE_CLASS: dict[str, str] = {
    "EMPTY_CAPTURE": "NEEDS_DATA",
    "NEEDS_EXACT_RULE_EXTRACTION": "NEEDS_RULE",
    "NEEDS_SYMBOL_EXTRACTION": "NEEDS_RULE",
    "OPERATIONAL_ROW": "NONE",
    "BANNED_FAMILY": "NONE",
}
#: The head of a worked-ledger disposition (the text before the first colon) -> its class.
#: Any head not listed and not RECOVERED_* ended without a candidate and without a terminal
#: refusal -- a seat outage, a rule miss, a rejection -- and still owes a rule.
WORKED_CLASS: dict[str, str] = {
    "REFUSED_NO_BODY_CAPTURED": "NEEDS_DATA",
    "REFUSED_OPERATIONAL_ROW": "NONE",
    "REFUSED_BANNED_FAMILY": "NONE",
}
#: Time bases that are a producer's own stamp. Anything else cannot place a row point-in-time.
_NO_PIT_BASES = frozenset({"", "artifact_mtime"})

#: Who can pay each class, in the repo's own paths. Published with the debt.
DRIVER: dict[str, str] = {
    "NEEDS_DATA": ("desks/mt5/side_channels/world_crawler.py (conversion_debt_seeds: recapture "
                   "on hosts its frontier already holds)"),
    "NEEDS_RULE": "desks/mt5/research/deepening_worker.py (hourly leg `deepening`)",
    "NEEDS_PIT": ("desks/mt5/side_channels/world_crawler.py (a recapture is vaulted with its "
                  "fetch time and content hash)"),
}

#: Addresses offered per pass. The crawler takes far fewer per run (its own cap); the file holds
#: more so that addresses already on the frontier do not starve the ones behind them.
MAX_SEEDS = 500
#: Distinct debt rows held in memory. Past this the pass is PARTIAL and says so.
MAX_ROWS = 2_000_000
TOP = 40


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True, default=str)
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def task_id(source: Any, url: Any, title: Any) -> str:
    """The deepening worker's durable row identity, exactly (`deepening_worker.task_id`)."""
    return hashlib.sha256(f"{source}|{url}|{title}".encode()).hexdigest()[:16]


def _http(url: Any) -> str:
    s = str(url or "").split("#")[0].strip()
    return s if s.startswith(("http://", "https://")) and urlparse(s).netloc else ""


def classify_queue(task: dict[str, Any]) -> str:
    """The class a QUEUED row owes: NEEDS_DATA, NEEDS_RULE, NONE or UNCLASSIFIED."""
    return QUEUE_CLASS.get(str(task.get("disposition") or ""), "UNCLASSIFIED")


def classify_worked(disposition: str, n_candidates: Any = 0) -> str:
    """The class a WORKED row owes after the deepening worker decided it."""
    head = disposition.split(":")[0].strip()
    try:
        produced = int(n_candidates or 0) > 0
    except (TypeError, ValueError):
        produced = False
    if produced or head.startswith("RECOVERED_"):
        return "NONE"
    if not head:
        return "UNCLASSIFIED"
    return WORKED_CLASS.get(head, "NEEDS_RULE")


def needs_pit(task: dict[str, Any]) -> bool | None:
    """True when a queued row carries no producer time stamp; None when the row cannot say.

    The compiler writes `retrieved_at_basis` on every task it queues. A task queued by a build
    before that field existed carries neither key, and is UNMEASURED rather than assumed clean.
    """
    if "retrieved_at_basis" not in task:
        return None if task.get("retrieved_at") else True
    return str(task.get("retrieved_at_basis") or "") in _NO_PIT_BASES


def load_frontier(path: Path | None = None) -> dict[str, Any]:
    """The crawler's frontier as {urls: {url: last_fetched}, hosts: set} or status UNMEASURED."""
    p = path or FRONTIER
    doc = _read_json(p)
    if doc is None:
        return {"status": "UNMEASURED", "why": f"{p.name} is absent or unreadable on this host"}
    rows: Any = doc.get("sources") if isinstance(doc, dict) else doc
    if isinstance(rows, dict):
        rows = [dict(v, url=v.get("url") or k) for k, v in rows.items() if isinstance(v, dict)]
    if not isinstance(rows, list):
        return {"status": "UNMEASURED", "why": f"{p.name} carries no source list"}
    urls: dict[str, tuple[str, int]] = {}
    hosts: set[str] = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        u = str(r.get("url") or "").split("#")[0].strip()
        if not u:
            continue
        try:
            fetched = int(r.get("fetches") or 0)
        except (TypeError, ValueError):
            fetched = 0
        urls[u] = (str(r.get("last_fetched") or ""), fetched)
        hosts.add(str(r.get("host") or urlparse(u).netloc).lower())
    hosts.discard("")
    return {"status": "OK", "urls": urls, "hosts": hosts}


def route(url: str, since: str, frontier: dict[str, Any]) -> str:
    """Where one debt address stands with the crawler.

    NO_URL / UNMEASURED / RECAPTURED / PENDING / OFFERED / UNROUTED_HOST.
    """
    if not url:
        return "NO_URL"
    if frontier.get("status") != "OK":
        return "UNMEASURED"
    hit = frontier["urls"].get(url)
    if hit is not None:
        last, fetched = hit
        return "RECAPTURED" if fetched > 0 and last and last >= (since or "") else "PENDING"
    if urlparse(url).netloc.lower() in frontier["hosts"]:
        return "OFFERED"
    return "UNROUTED_HOST"


def _age_days(at: str, now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return round(max(0.0, (now - t).total_seconds()) / 86400.0, 2)


def build(*, queue: Path | None = None, worked: Path | None = None,
          frontier_path: Path | None = None, backlog: Path | None = None,
          budget_s: float = 240.0, now: datetime | None = None) -> tuple[dict[str, Any],
                                                                         dict[str, Any]]:
    """One pass. Returns (report, seeds document). Reads only; writes nothing."""
    now = now or _now()
    started = time.monotonic()
    notes: list[str] = []
    # id -> [class, source, at, url, pit]; pit is True / False / None (UNMEASURED).
    rows: dict[str, list[Any]] = {}
    partial = False

    # 1. THE WORKED LEDGER, streamed: the latest decision per row wins (append order).
    w = worked or WORKED
    worked_state: dict[str, Any] = {"path": w.name}
    try:
        n_lines = 0
        with w.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                n_lines += 1
                if n_lines % 20_000 == 0 and time.monotonic() - started > budget_s * 0.7:
                    partial = True
                    notes.append(f"{w.name}: budget reached after {n_lines} line(s); the rest "
                                 "is read on a pass with more budget")
                    break
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(item, dict):
                    continue
                tid = str(item.get("id") or "")
                if not tid:
                    continue
                cls = classify_worked(str(item.get("disposition") or ""),
                                      item.get("n_candidates"))
                prior = rows.get(tid)
                if prior is None and len(rows) >= MAX_ROWS:
                    partial = True
                    continue
                first_at = prior[2] if prior else str(item.get("at") or "")
                rows[tid] = [cls, str(item.get("source") or "unknown"), first_at,
                             _http(item.get("url")), None]
        worked_state.update(status="OK", lines=n_lines)
    except OSError as exc:
        worked_state.update(status="UNMEASURED", why=f"{type(exc).__name__}: {exc}"[:200])

    # 2. THE QUEUE: this window's rows. A queued row the worker has not decided takes the
    #    compiler's label; a decided one keeps the worker's, and gains the queue's time basis.
    q = queue or QUEUE
    qdoc = _read_json(q)
    tasks = qdoc.get("tasks") if isinstance(qdoc, dict) else None
    queue_state: dict[str, Any] = {"path": q.name}
    if not isinstance(tasks, list):
        queue_state.update(status="UNMEASURED", why=f"{q.name} is absent or carries no tasks")
        tasks = []
    else:
        queue_state.update(status="OK", tasks=len(tasks),
                           built_at=str(qdoc.get("built_at") or ""))
    built_at = str(queue_state.get("built_at") or now.isoformat(timespec="seconds"))
    for t in tasks:
        if not isinstance(t, dict):
            continue
        tid = task_id(t.get("source"), t.get("url"), t.get("title"))
        pit = needs_pit(t)
        prior = rows.get(tid)
        if prior is not None:
            prior[4] = pit
            prior[3] = prior[3] or _http(t.get("url")) or _http(t.get("source_url"))
            continue
        rows[tid] = [classify_queue(t), str(t.get("source") or "unknown"),
                     str(t.get("retrieved_at") or built_at),
                     _http(t.get("url")) or _http(t.get("source_url")), pit]

    # 3. THE LEDGER OF DEBT, per class and per source, and the route of every fetchable row.
    frontier = load_frontier(frontier_path)
    by_class: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = {}
    routes: dict[str, Counter[str]] = {c: Counter() for c in ("NEEDS_DATA", "NEEDS_PIT")}
    unrouted_hosts: Counter[str] = Counter()
    no_url_sources: Counter[str] = Counter()
    oldest: dict[str, str] = {}
    pit_unmeasured = 0
    owed_nothing = unclassified = 0
    offered: dict[str, tuple[str, str, str]] = {}          # url -> (since, class, source)
    for cls, source, at, url, pit in rows.values():
        if cls == "NONE":
            owed_nothing += 1
            continue
        if cls == "UNCLASSIFIED":
            unclassified += 1
            continue
        owes = [cls]
        if pit is True:
            owes.append("NEEDS_PIT")
        elif pit is None:
            pit_unmeasured += 1
        src = by_source.setdefault(source, Counter())
        for c in owes:
            by_class[c] += 1
            src[c] += 1
            if at and (c not in oldest or at < oldest[c]):
                oldest[c] = at
            if c not in routes:
                continue
            r = route(url, at, frontier)
            routes[c][r] += 1
            if r == "UNROUTED_HOST":
                unrouted_hosts[urlparse(url).netloc.lower()] += 1
            elif r == "NO_URL":
                no_url_sources[source] += 1
            elif r == "OFFERED" and (url not in offered or at < offered[url][0]):
                offered[url] = (at, c, source)

    # Oldest debt first: a row that has waited longest is offered before a newer one.
    ranked = sorted(offered.items(), key=lambda kv: (kv[1][0], kv[0]))
    seed_rows = [{"url": u, "since": s, "class": c, "source": src}
                 for u, (s, c, src) in ranked[:MAX_SEEDS]]
    seeds = {
        "built_at": now.isoformat(timespec="seconds"),
        "consumer": "desks/mt5/side_channels/world_crawler.py conversion_debt_seeds()",
        "rule": ("addresses of mined rows that have nothing to read or no point-in-time stamp, "
                 "on hosts the crawler's frontier already holds; the crawler adds them under "
                 "its own cap and fetches them under its own budget, host gap and terms label"),
        "frontier": frontier.get("status"),
        "urls": [r["url"] for r in seed_rows],
        "rows": seed_rows,
        "offered_total": len(offered),
    }

    bdoc = _read_json(backlog or BACKLOG)
    rule_driver = ({"status": "OK", "depth": bdoc.get("depth", bdoc.get("backlog")),
                    "oldest_age_h": bdoc.get("oldest_age_h", bdoc.get("oldest_age_hours")),
                    "at": bdoc.get("at") or bdoc.get("generated_at") or bdoc.get("built_at")}
                   if isinstance(bdoc, dict) else
                   {"status": "UNMEASURED", "why": "DEEPENING_BACKLOG.json absent on this host"})

    debt_rows = sum(1 for r in rows.values() if r[0] in CLASSES)
    undriven = (routes["NEEDS_DATA"]["UNROUTED_HOST"] + routes["NEEDS_DATA"]["NO_URL"]
                + routes["NEEDS_DATA"]["UNMEASURED"])
    inputs_ok = worked_state.get("status") == "OK" or queue_state.get("status") == "OK"
    report: dict[str, Any] = {
        "generated_at": now.isoformat(timespec="seconds"),
        "status": ("UNMEASURED" if not inputs_ok else "PARTIAL" if partial else "OK"),
        "rule": ("every unconverted mined row owes exactly what an organ already named: a fetch "
                 "(NEEDS_DATA), a reader (NEEDS_RULE), a point-in-time stamp (NEEDS_PIT, in "
                 "addition). Converted rows and named terminal refusals owe nothing."),
        "inputs": {"worked": worked_state, "queue": queue_state,
                   "frontier": {k: v for k, v in frontier.items() if k in ("status", "why")}
                   | ({"sources": len(frontier["urls"]), "hosts": len(frontier["hosts"])}
                      if frontier.get("status") == "OK" else {})},
        "rows_seen": len(rows),
        "rows_in_debt": debt_rows,
        "rows_owing_nothing": owed_nothing,
        "rows_unclassified": unclassified,
        "debt": {c: {"rows": int(by_class.get(c, 0)),
                     "oldest_at": oldest.get(c),
                     "oldest_age_days": _age_days(oldest[c], now) if c in oldest else None,
                     "driver": DRIVER[c]} for c in CLASSES},
        "needs_pit_unmeasured_rows": pit_unmeasured,
        "needs_pit_basis": ("a queued row whose compiler task says retrieved_at_basis is "
                            "artifact_mtime or empty; worked rows no longer in the queue carry "
                            "no basis and are counted in needs_pit_unmeasured_rows"),
        "drive": {
            "NEEDS_DATA": dict(routes["NEEDS_DATA"]),
            "NEEDS_PIT": dict(routes["NEEDS_PIT"]),
            "NEEDS_RULE": rule_driver,
            "seeds_offered": len(seed_rows),
            "seeds_waiting_behind_cap": max(0, len(offered) - len(seed_rows)),
            "undriven_needs_data_rows": int(undriven),
            "unrouted_hosts": [{"host": h, "rows": n}
                               for h, n in unrouted_hosts.most_common(TOP)],
            "no_url_owed_by_source": [{"source": s, "rows": n}
                                      for s, n in no_url_sources.most_common(TOP)],
            "meaning": {
                "RECAPTURED": "the frontier shows a fetch of the address since the row entered "
                              "debt; the crawler's row for it now goes through the compiler",
                "PENDING": "on the frontier, not fetched since the row entered debt",
                "OFFERED": "host is on the frontier; the address is in the seeds file",
                "UNROUTED_HOST": "the crawler does not work this host; nothing fetches it",
                "NO_URL": "the row names no http(s) address; owed by its producing miner",
                "UNMEASURED": "the frontier is not readable on this host; no seed offered",
            },
        },
        "per_source": [{"source": s, **{c: int(n.get(c, 0)) for c in CLASSES}}
                       for s, n in sorted(by_source.items(),
                                          key=lambda kv: -sum(kv[1].values()))[:TOP]],
        "sources_in_debt": len(by_source),
        "notes": notes,
        "elapsed_s": round(time.monotonic() - started, 2),
    }
    return report, seeds


def summary(doc: dict[str, Any]) -> str:
    d = doc.get("debt") or {}
    drive = doc.get("drive") or {}
    return (f"conversion debt [{doc.get('status')}]: "
            + ", ".join(f"{c} {int((d.get(c) or {}).get('rows') or 0)}" for c in CLASSES)
            + f" | seeds offered {drive.get('seeds_offered')}, recaptured "
              f"{(drive.get('NEEDS_DATA') or {}).get('RECAPTURED', 0)}, undriven "
              f"{drive.get('undriven_needs_data_rows')}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print the report; write nothing")
    ap.add_argument("--budget-s", type=float, default=240.0)
    args = ap.parse_args(argv)
    budget = args.budget_s
    try:
        leg = float(os.environ.get("QUANT_LEG_BUDGET_S") or 0)
    except ValueError:
        leg = 0.0
    if leg > 0:
        budget = min(budget, leg * 0.8)
    report, seeds = build(budget_s=budget)
    print(summary(report), flush=True)
    if args.dry_run:
        return 0
    _atomic(SEEDS, seeds)
    _atomic(OUT, report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
