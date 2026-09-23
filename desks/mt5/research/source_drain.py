"""THE DRAIN GUARANTEE -- every registered source collected, chained and converted, or named.

THE PRINCIPAL, 2026-09-23: *"make sure they are always collected, 100% exploited and converted."*
`source_evig` prices the queue; pricing ORDERS a backlog and never drains one, and a source that is
never fetched has an information gain of exactly zero however well it is ranked. On the first
priced pass 147 of 155 sources had never been collected.

WHAT THIS ORGAN GUARANTEES, and each clause is a number it publishes.

  1. THE BACKLOG FALLS EVERY PASS. The top of the EVIG ranking that has never been collected is
     handed to `asia_collector --id ...` this cycle, until the backlog is empty. `n_uncollected`,
     the OLDEST never-collected source and the measured drain rate (sources per pass, and the
     passes remaining at that rate) are published every pass.
  2. UNREACHABLE IS RECORDED, NEVER SILENT. A source that genuinely cannot be fetched lands in
     `not_reached` with the url tried, the status the collector recorded and the attempt count.
     Absence of a row is the one thing this organ does not allow.
  3. A CHAIN, NOT A FETCH. Per source: COLLECTED (bytes in the vault) -> INGESTED (a series with
     a PIT vintage and availability stamp) -> REPRESENTED (rows in that series) -> CELLS_EMITTED
     (candidates the registry credits to it) -> CELLS_JUDGED (those the one gauntlet judged). A
     source that stops at bytes is as useless as one never fetched, and the stage it stopped at
     is the published reason.
  4. TWO RATCHETS THAT ONLY FALL, in `data/source_drain_ratchet.json`: `uncollected` and
     `collected_but_unconverted`. `scripts/check_source_drain.py` fails when either RISES above
     its own best, or when the oldest never-collected source ages past its own cadence window.
  5. THE NUMBER TO MAXIMISE is CELLS REACHING THE GAUNTLET PER SOURCE. A source that is collected
     and represented and still emits nothing gets its reason named and a task: REBUILD (the
     representation exists to be fixed) or RETIRE (nothing to represent), appended to
     `data/source_rebuild_tasks.jsonl`. Never a quiet zero.

NOTHING HERE IS A CAP. It only ever causes MORE collection and MORE conversion; no source is
throttled, no fetch is refused, and the fence fails on a RISING backlog, never on a growing one
that is being worked.

    python desks/mt5/research/source_drain.py --once --budget-s 300 [--no-fetch]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = DESK / "data" / "asia_sources.json"
STATE = DESK / "data" / "lake" / "collector_state.json"
VAULT = DESK / "data" / "lake" / "vault"
SERIES = DESK / "data" / "lake" / "series"
SOURCE_REGISTRY = DESK / "reports" / "SOURCE_REGISTRY.json"
EVIG = DESK / "reports" / "SOURCE_EVIG.json"
RATCHET = DESK / "data" / "source_drain_ratchet.json"
TASKS = DESK / "data" / "source_rebuild_tasks.jsonl"
OUT = DESK / "reports" / "SOURCE_DRAIN.json"

COLLECTOR = DESK / "research" / "asia_collector.py"
BATCH = 12                 # sources handed to the collector per pass; raised by budget, never cut
OK_STATUSES = ("COLLECTED", "UNCHANGED", "NOT_MODIFIED")
STAGES = ("collected", "ingested", "represented", "cells_emitted", "cells_judged")
#: Declared cadence -> the hours a source may go uncollected before the fence calls it stale.
#: Three times its own publication cadence: a monthly release missing for a quarter is a defect.
WINDOW_H: dict[str, float] = {"realtime": 3.0, "intraday": 18.0, "daily": 144.0,
                              "weekly": 1_008.0, "monthly": 4_320.0, "quarterly": 12_960.0,
                              "irregular": 6_480.0}


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def _sources() -> list[dict[str, Any]]:
    reg = _read(REGISTRY, {}) or {}
    rows = reg.get("sources") if isinstance(reg, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("id")
            and str(r.get("role") or "mechanism") != "transport"]


def _credited() -> tuple[dict[str, dict[str, int]], str]:
    """Cells the source registry credits to a source id, by exact or namespaced match."""
    doc = _read(SOURCE_REGISTRY, {}) or {}
    rows: list[dict[str, Any]] = []
    for key in ("top_by_roi", "top_by_reputation", "sources", "rows"):
        v = doc.get(key)
        if isinstance(v, list):
            rows.extend(r for r in v if isinstance(r, dict))
    if not rows:
        return {}, "no reports/SOURCE_REGISTRY.json rows on this host"
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        sid = str(r.get("source_id") or r.get("id") or "")
        if not sid:
            continue
        out[sid.split(":")[-1]] = {"leads": int(r.get("n_leads") or 0),
                                   "testable": int(r.get("n_testable") or 0),
                                   "judged": int(r.get("n_certified") or 0)}
    return out, ""


def chain_for(src: dict[str, Any], state: dict[str, Any],
              credited: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Where this source stands in the whole chain, one row, every stage measured."""
    sid = str(src.get("id"))
    _row = state.get(sid)
    row: dict[str, Any] = dict(_row) if isinstance(_row, dict) else {}
    status = str(row.get("last_status") or "")
    vault_hit = (VAULT / sid).exists()
    collected = bool(status in OK_STATUSES or vault_hit)
    series = next((p for p in (SERIES / f"{sid}.parquet", SERIES / f"{sid}.json",
                               SERIES / f"{sid}.csv") if p.exists()), None)
    pit = SERIES / f"{sid}.pit.json"
    pit_doc = _read(pit, {}) if pit.exists() else {}
    ingested = bool(series is not None and isinstance(pit_doc, dict) and pit_doc)
    n_rows = 0
    if isinstance(pit_doc, dict):
        for k in ("n_rows", "rows", "n"):
            try:
                n_rows = int(pit_doc.get(k))  # type: ignore[arg-type]
                break
            except (TypeError, ValueError):
                continue
    if not n_rows and series is not None:
        try:
            n_rows = 1 if series.stat().st_size > 64 else 0
        except OSError:
            n_rows = 0
    represented = bool(ingested and n_rows > 0)
    cells = credited.get(sid) or {}
    emitted = int(cells.get("testable") or cells.get("leads") or 0)
    judged = int(cells.get("judged") or 0)
    reached = "none"
    for stage, ok in (("collected", collected), ("ingested", ingested),
                      ("represented", represented), ("cells_emitted", emitted > 0),
                      ("cells_judged", judged > 0)):
        if not ok:
            break
        reached = stage
    if reached == "none":
        stops_at: str | None = STAGES[0]
    elif reached == STAGES[-1]:
        stops_at = None
    else:
        stops_at = STAGES[STAGES.index(reached) + 1]
    return {
        "id": sid, "cadence": src.get("cadence"), "url": src.get("url"),
        "targets": src.get("targets") or [],
        "collected": collected, "ingested": ingested, "represented": represented,
        "n_rows": n_rows,
        "cells_emitted": emitted, "cells_judged": judged,
        "cells_basis": ("SOURCE_REGISTRY credit" if cells else "no registry credit row"),
        "stage_reached": reached, "stops_at": stops_at,
        "last_status": status or None,
        "last_attempt_epoch": row.get("last_attempt_epoch"),
        "why": (
            "never collected: no vault blob and no successful collector status" if not collected
            else "collected but never ingested: bytes landed and no series with a PIT stamp "
                 "was written" if not ingested
            else "ingested but empty: the series exists and carries no rows" if not represented
            else "represented and no cell was ever credited to it" if emitted <= 0
            else "cells emitted and none judged by the gauntlet" if judged <= 0
            else "converted: cells reached the one gauntlet"),
    }


def _window_h(src: dict[str, Any]) -> float:
    return WINDOW_H.get(str(src.get("cadence") or "irregular").lower(), 6_480.0)


def _evig_order(ids: list[str]) -> list[str]:
    try:
        from research.source_evig import fetch_order
        return [i for i in fetch_order(ids) if i in set(ids)]
    except Exception:
        return list(ids)


def drain(pending: list[str], budget_s: float, *, fetch: bool = True,
          oldest_first: list[str] | None = None) -> dict[str, Any]:
    """Hand the top of the ranking to the collector, this pass, and record what answered."""
    if not pending:
        return {"attempted": [], "n_attempted": 0, "seconds": 0.0,
                "why": "backlog empty: every registered source has been collected"}
    if not fetch:
        return {"attempted": [], "n_attempted": 0, "seconds": 0.0,
                "why": "--no-fetch: the queue was priced and nothing was requested"}
    oldest_first = oldest_first or []
    # HALF BY PRICE, HALF BY AGE, so the tail can never starve. A pure top-of-ranking batch
    # re-requests the same twelve sources every hour -- the same truncated-prefix defect that
    # cost this desk eighty-four forward clocks -- and a source that fails twice would then be
    # retried forever while one never attempted at all waits behind it. `pending` arrives in
    # EVIG order and `oldest_first` is the least-recently-attempted half, so every uncollected
    # source is reached within ceil(backlog / (BATCH/2)) passes whatever its price.
    head = pending[: max(1, BATCH // 2)]
    tail = [sid for sid in oldest_first if sid not in head][: BATCH - len(head)]
    batch = [*head, *tail]
    args: list[str] = [sys.executable, str(COLLECTOR)]
    for sid in batch:
        args += ["--id", sid]
    args += ["--budget", str(max(30.0, budget_s)), "--timeout", "20"]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=max(60.0, budget_s + 60.0), check=False, cwd=str(DESK))
        tail = (proc.stdout or "").strip().splitlines()[-6:]
        rc: int | None = proc.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        tail, rc = [f"{type(exc).__name__}: {exc}"], None
    return {"attempted": batch, "n_attempted": len(batch), "returncode": rc,
            "seconds": round(time.monotonic() - t0, 2), "collector_tail": tail,
            "why": ("half the batch by EVIG and half by staleness, so the tail of the "
                    "backlog cannot starve behind a source that fails every hour")}


def _tasks(rows: list[dict[str, Any]], now: str) -> list[dict[str, Any]]:
    """A named task per collected-but-unconverted source. Never a quiet zero."""
    out: list[dict[str, Any]] = []
    for r in rows:
        if not r["collected"] or r["cells_judged"] > 0:
            continue
        kind = ("REBUILD" if r["ingested"] or r["represented"] else
                ("REBUILD" if r["collected"] else "RETIRE"))
        if r["collected"] and not r["ingested"]:
            kind = "REBUILD"          # bytes exist: the parser is what is missing
        if r["represented"] and r["cells_emitted"] <= 0:
            kind = "REBUILD"          # rows exist: a family or a mapping is what is missing
        out.append({"at": now, "id": r["id"], "task": kind, "stops_at": r["stops_at"],
                    "why": r["why"], "url": r["url"], "targets": r["targets"]})
    return out


def build(budget_s: float = 300.0, *, fetch: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    srcs = _sources()
    state = _read(STATE, {}) or {}
    credited, credit_why = _credited()
    rows = [chain_for(s, state if isinstance(state, dict) else {}, credited) for s in srcs]
    by_id = {r["id"]: r for r in rows}
    ratchet = _read(RATCHET, {}) or {}
    first_seen: dict[str, str] = dict(ratchet.get("first_seen") or {})

    uncollected_before = [r["id"] for r in rows if not r["collected"]]
    for sid in uncollected_before:
        first_seen.setdefault(sid, now)
    ages = []
    for sid in uncollected_before:
        try:
            seen = datetime.fromisoformat(str(first_seen[sid]).replace("Z", "+00:00"))
            ages.append((sid, (datetime.now(tz=UTC) - seen).total_seconds() / 3600.0))
        except ValueError:
            continue
    oldest = max(ages, key=lambda kv: kv[1], default=(None, 0.0))
    windows = {str(s.get("id")): _window_h(s) for s in srcs}

    pending = _evig_order(uncollected_before)
    # The least-recently-attempted never-collected sources, for the anti-starvation half.
    def _last_attempt(sid: str) -> float:
        row = state.get(sid) if isinstance(state, dict) else None
        try:
            return float(row.get("last_attempt_epoch"))  # type: ignore[union-attr]
        except (TypeError, ValueError, AttributeError):
            return 0.0

    oldest_first = sorted(uncollected_before, key=_last_attempt)
    result = drain(pending, min(budget_s * 0.7, 180.0), fetch=fetch,
                   oldest_first=oldest_first)

    state_after = _read(STATE, {}) or {}
    rows_after = [chain_for(s, state_after if isinstance(state_after, dict) else {}, credited)
                  for s in srcs]
    by_id_after = {r["id"]: r for r in rows_after}
    uncollected_after = [r["id"] for r in rows_after if not r["collected"]]
    drained = [sid for sid in result.get("attempted") or []
               if by_id_after.get(sid, {}).get("collected")]
    def _status_of(sid: str) -> Any:
        row_after = state_after.get(sid) if isinstance(state_after, dict) else None
        return row_after.get("last_status") if isinstance(row_after, dict) else None

    not_reached = [{"id": sid, "url": by_id.get(sid, {}).get("url"),
                    "collector_status": _status_of(sid),
                    "attempted_at": now,
                    "why": "requested this pass and still uncollected; it leads the next pass"}
                   for sid in (result.get("attempted") or []) if sid not in drained]

    collected_after = [r for r in rows_after if r["collected"]]
    unconverted = [r for r in collected_after if r["cells_judged"] <= 0]
    tasks = _tasks(rows_after, now)
    if tasks:
        TASKS.parent.mkdir(parents=True, exist_ok=True)
        with TASKS.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(t, default=str) for t in tasks) + "\n")

    history = list(ratchet.get("history") or [])[-49:]
    history.append({"at": now, "uncollected": len(uncollected_after),
                    "unconverted": len(unconverted), "drained": len(drained)})
    rate = 0.0
    if len(history) >= 2:
        span = history[0]["uncollected"] - history[-1]["uncollected"]
        rate = round(span / max(len(history) - 1, 1), 3)
    best_unc = min(int(ratchet.get("best_uncollected", 10**9)), len(uncollected_after))
    best_conv = min(int(ratchet.get("best_unconverted", 10**9)), len(unconverted))
    _write(RATCHET, {"at": now, "best_uncollected": best_unc, "best_unconverted": best_conv,
                     "uncollected": len(uncollected_after), "unconverted": len(unconverted),
                     "oldest_never_collected": oldest[0],
                     "oldest_age_h": round(oldest[1], 2),
                     "oldest_window_h": windows.get(str(oldest[0]), 6_480.0),
                     "first_seen": first_seen, "history": history,
                     "rule": ("both counts are RATCHETS: check_source_drain.py fails when either "
                              "rises above its own best, or when the oldest never-collected "
                              "source ages past its own cadence window")})

    stages: dict[str, int] = {}
    for r in rows_after:
        stages[str(r["stage_reached"])] = stages.get(str(r["stage_reached"]), 0) + 1
    zero_cell_top = [
        {"id": r["id"], "evig_rank": pending.index(r["id"]) if r["id"] in pending else None,
         "stage_reached": r["stage_reached"], "why": r["why"]}
        for r in sorted(rows_after, key=lambda r: (r["cells_judged"], r["cells_emitted"]))
        if r["cells_emitted"] <= 0][:5]

    return {
        "at": now,
        "status": "OK" if rows_after else "UNMEASURED",
        "n_sources": len(rows_after),
        "uncollected_before": len(uncollected_before),
        "uncollected_after": len(uncollected_after),
        "n_drained_this_pass": len(drained), "drained": drained,
        "drain_rate_per_pass": rate,
        "passes_to_empty": (round(len(uncollected_after) / rate, 1) if rate > 0 else None),
        "oldest_never_collected": {"id": oldest[0], "age_h": round(oldest[1], 2),
                                   "window_h": windows.get(str(oldest[0]), 6_480.0)},
        "not_reached": not_reached,
        "chain": {"stages": STAGES, "census": stages},
        "n_collected": len(collected_after),
        "n_collected_but_unconverted": len(unconverted),
        "n_cells_judged_total": sum(int(r["cells_judged"]) for r in rows_after),
        "cells_credit_basis": credit_why or "SOURCE_REGISTRY per-source credit",
        "highest_evig_at_zero_cells": zero_cell_top,
        "tasks_appended": len(tasks),
        "rows": rows_after,
        "collector": result,
        "consumers": [
            "scripts/check_source_drain.py -> the two ratchets and the oldest-source window; the "
            "law gate fails when a backlog RISES",
            "desks/mt5/data/source_rebuild_tasks.jsonl -> one named REBUILD/RETIRE task per "
            "collected-but-unconverted source, re-read by this organ each pass",
            "desks/mt5/research/asia_collector.py -> the sources this pass requested by id",
        ],
        "boundary": (
            "THIS ONLY EVER CAUSES MORE COLLECTION. No source is throttled, disabled or refused; "
            "the fence fails on a RISING backlog, never on a large one that is being worked."),
        "seconds": round(time.monotonic() - t0, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--no-fetch", action="store_true",
                    help="measure the chain and the ratchets without requesting a collection")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, fetch=not a.no_fetch)
    try:
        _write(OUT, doc)
    except OSError as exc:
        print(f"source drain: could not write {OUT}: {exc}")
        return 1
    print(f"source drain: uncollected {doc['uncollected_before']} -> "
          f"{doc['uncollected_after']} ({doc['n_drained_this_pass']} drained this pass, rate "
          f"{doc['drain_rate_per_pass']}/pass, {doc['passes_to_empty']} passes to empty)")
    o = doc["oldest_never_collected"]
    print(f"  oldest never collected: {o['id']} at {o['age_h']}h of a {o['window_h']}h window")
    print(f"  chain census: {doc['chain']['census']}")
    print(f"  collected {doc['n_collected']}, of which {doc['n_collected_but_unconverted']} "
          f"unconverted; {doc['n_cells_judged_total']} cell(s) judged in total; "
          f"{doc['tasks_appended']} task(s) appended")
    for r in doc["highest_evig_at_zero_cells"]:
        print(f"   ZERO CELLS {str(r['id'])[:32]:<32} rank={r['evig_rank']} "
              f"stage={r['stage_reached']} -- {r['why'][:60]}")
    for r in doc["not_reached"][:6]:
        print(f"   NOT_REACHED {str(r['id'])[:30]:<30} status={r['collector_status']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
